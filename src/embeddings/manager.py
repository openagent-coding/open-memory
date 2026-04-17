from __future__ import annotations

import logging

from ..config import Settings
from .classifier import ContentClassifier
from .models import EmbeddingModel

logger = logging.getLogger(__name__)


class EmbeddingManager:
    def __init__(self, settings: Settings):
        self._primary = EmbeddingModel(
            settings.embedding_model, settings.embedding_dim, settings.device
        )
        self._dual = settings.dual_embedding
        self._code_model: EmbeddingModel | None = None
        if self._dual:
            self._code_model = EmbeddingModel(
                settings.code_embedding_model, settings.code_embedding_dim, settings.device
            )
            self._classifier = ContentClassifier()

    @property
    def primary_available(self) -> bool:
        return self._primary.available

    @property
    def code_available(self) -> bool:
        return self._code_model is not None and self._code_model.available

    @property
    def dual_mode(self) -> bool:
        return self._dual

    async def initialize(self) -> None:
        ok = await self._primary.warmup()
        if not ok:
            logger.warning("Primary embedding model unavailable — search/dedup disabled")

        if self._code_model:
            code_ok = await self._code_model.warmup()
            if not code_ok:
                logger.warning("Code embedding model unavailable — code search disabled")
            else:
                logger.info("Dual embedding mode active")
        else:
            logger.info("Single embedding mode active")

    async def embed(self, content: str) -> tuple[list[float] | None, list[float] | None]:
        primary_emb: list[float] | None = None
        code_emb: list[float] | None = None

        if self._primary.available:
            result = await self._primary.encode([content])
            if result:
                primary_emb = result[0]

        if self._dual and self._code_model and self._code_model.available:
            from .classifier import ContentClassifier
            content_type = self._classifier.classify(content)
            if content_type.value in ("code", "mixed"):
                result = await self._code_model.encode([content])
                if result:
                    code_emb = result[0]

        return primary_emb, code_emb
