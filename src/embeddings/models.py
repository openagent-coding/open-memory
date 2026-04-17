from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingModel:
    _executor = ThreadPoolExecutor(max_workers=2)
    _semaphore = asyncio.Semaphore(2)

    def __init__(self, model_name: str, dim: int | None, device: str = "cpu"):
        self._model: Any = None
        self._model_name = model_name
        self._dim = dim
        self._device = device
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer

            kwargs: dict[str, Any] = {
                "trust_remote_code": True,
                "device": self._device,
            }
            if self._dim is not None:
                kwargs["truncate_dim"] = self._dim

            self._model = SentenceTransformer(self._model_name, **kwargs)
            logger.info(
                "Loaded embedding model %s (dim=%s, device=%s)",
                self._model_name, self._dim, self._device,
            )
        except Exception:
            self._available = False
            logger.exception("Failed to load embedding model %s", self._model_name)

    async def encode(self, texts: list[str]) -> list[list[float]]:
        self._load()
        if not self._available or self._model is None:
            return []
        async with self._semaphore:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self._executor,
                lambda: self._model.encode(texts, normalize_embeddings=True),
            )
        if isinstance(result, np.ndarray):
            return result.tolist()
        return [list(r) for r in result]

    async def warmup(self) -> bool:
        try:
            embeddings = await self.encode(["warmup"])
            if embeddings:
                logger.info("Model %s warmed up, dim=%d", self._model_name, len(embeddings[0]))
                return True
        except Exception:
            self._available = False
            logger.exception("Warmup failed for %s", self._model_name)
        return False
