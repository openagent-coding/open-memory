from __future__ import annotations

import logging
from typing import Any

from ..config import Settings
from ..database.base import MemoryDatabase

logger = logging.getLogger(__name__)


class DedupService:
    def __init__(self, db: MemoryDatabase, settings: Settings):
        self._db = db
        self._threshold = settings.similarity_threshold

    async def find_duplicate(
        self,
        memory_type: str,
        entity_key: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
    ) -> dict[str, Any] | None:
        candidates = await self._db.find_similar(
            memory_type, entity_key, embedding, code_embedding, self._threshold
        )
        if not candidates:
            return None
        best = max(candidates, key=lambda c: c.get("similarity", 0))
        logger.debug(
            "Found duplicate in %s (similarity=%.3f): %s",
            memory_type, best["similarity"], best["id"],
        )
        return best

    @staticmethod
    def merge_content(existing: str, new: str, similarity: float) -> str:
        if similarity >= 0.90:
            return new
        return f"{existing}\n\n---\n\n{new}"
