from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..config import Settings
from ..database.base import MemoryDatabase
from ..embeddings.manager import EmbeddingManager
from ..schemas import (
    MemoryEntry,
    MemoryType,
    SaveMemoryResponse,
    SearchResult,
)
from .consolidation import ConsolidationService
from .dedup import DedupService

logger = logging.getLogger(__name__)


class MemoryService:
    def __init__(
        self, db: MemoryDatabase, embeddings: EmbeddingManager, settings: Settings
    ):
        self._db = db
        self._embeddings = embeddings
        self._settings = settings
        self._dedup = DedupService(db, settings)
        self._consolidation = ConsolidationService(db, embeddings, settings)

    async def save_memory(
        self,
        memory_type: MemoryType,
        entity_key: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> SaveMemoryResponse:
        emb, code_emb = await self._embeddings.embed(content)

        lock_key = hash((memory_type.value, entity_key)) & 0x7FFFFFFFFFFFFFFF
        async with self._db.advisory_lock(lock_key):
            existing = await self._dedup.find_duplicate(
                memory_type.value, entity_key, emb, code_emb
            )

            if existing:
                similarity = existing.get("similarity", 0.85)
                merged_content = DedupService.merge_content(
                    existing["content"], content, similarity
                )
                merged_metadata = {**(existing.get("metadata") or {}), **(metadata or {})}

                if merged_content == content:
                    new_emb, new_code_emb = emb, code_emb
                else:
                    new_emb, new_code_emb = await self._embeddings.embed(merged_content)

                await self._db.update_memory(
                    existing["id"],
                    merged_content,
                    merged_metadata,
                    existing.get("content_type", "text"),
                    new_emb,
                    new_code_emb,
                )
                logger.info("Merged memory into %s (%s)", existing["id"], memory_type.value)
                return SaveMemoryResponse(
                    id=existing["id"], action="merged", merged_with_id=existing["id"]
                )

            new_id = await self._db.insert_memory(
                memory_type.value, entity_key, content,
                metadata or {}, "text", emb, code_emb,
            )

        cap = self._settings.cap_for_type(memory_type.value)
        await self._db.enforce_cap(memory_type.value, entity_key, cap)

        logger.info("Inserted memory %s (%s)", new_id, memory_type.value)
        return SaveMemoryResponse(id=new_id, action="inserted")

    async def get_memory(
        self, memory_type: MemoryType, entity_key: str, limit: int = 10
    ) -> list[MemoryEntry]:
        limit = min(limit, 500)
        records = await self._db.get_memories(memory_type.value, entity_key, limit)
        if records:
            try:
                await self._db.touch_memories([r["id"] for r in records])
            except Exception:
                logger.debug("Failed to update access tracking", exc_info=True)
        return [MemoryEntry(**r) for r in records]

    async def search_memory(
        self,
        query: str,
        memory_types: list[MemoryType] | None = None,
        entity_key: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[SearchResult]:
        limit = min(limit, 500)
        emb, code_emb = await self._embeddings.embed(query)

        coros = []

        if emb:
            if memory_types:
                for mt in memory_types:
                    coros.append(
                        self._db.search_by_embedding(
                            emb, mt.value, entity_key, limit, min_similarity
                        )
                    )
            else:
                coros.append(
                    self._db.search_by_embedding(
                        emb, None, entity_key, limit, min_similarity
                    )
                )

        if code_emb:
            if memory_types:
                for mt in memory_types:
                    coros.append(
                        self._db.search_by_code_embedding(
                            code_emb, mt.value, entity_key, limit, min_similarity
                        )
                    )
            else:
                coros.append(
                    self._db.search_by_code_embedding(
                        code_emb, None, entity_key, limit, min_similarity
                    )
                )

        if not coros:
            return []

        result_lists = await asyncio.gather(*coros)

        if len(result_lists) > 1:
            fused = self._reciprocal_rank_fusion(*result_lists, k=60)
        elif result_lists:
            fused = result_lists[0]
        else:
            fused = []

        results = [
            SearchResult(
                entry=MemoryEntry(**{k: v for k, v in r.items() if k != "similarity"}),
                similarity=r.get("similarity", 0.0),
            )
            for r in fused[:limit]
        ]

        ids = [r.entry.id for r in results]
        if ids:
            try:
                await self._db.touch_memories(ids)
            except Exception:
                logger.debug("Failed to update access tracking", exc_info=True)

        return results

    @staticmethod
    def _reciprocal_rank_fusion(
        *result_lists: list[dict[str, Any]], k: int = 60
    ) -> list[dict[str, Any]]:
        scores: dict[str, float] = {}
        entries: dict[str, dict[str, Any]] = {}

        for results in result_lists:
            for rank, entry in enumerate(results):
                entry_id = entry["id"]
                scores[entry_id] = scores.get(entry_id, 0.0) + 1.0 / (k + rank + 1)
                if entry_id not in entries:
                    entries[entry_id] = entry.copy()

        fused = []
        for entry_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            e = entries[entry_id]
            e["similarity"] = score
            fused.append(e)
        return fused

    async def delete_memory(self, memory_id: str) -> bool:
        return await self._db.delete_memory(memory_id)

    async def consolidate(
        self, memory_type: MemoryType, entity_key: str, threshold: float = 0.80
    ) -> int:
        return await self._consolidation.consolidate(memory_type.value, entity_key, threshold)

    async def get_stats(self, entity_key: str | None = None) -> dict[str, Any]:
        stats: dict[str, Any] = {}
        for mt in MemoryType:
            entry: dict[str, Any] = {"cap": self._settings.cap_for_type(mt.value)}
            if entity_key:
                entry["count"] = await self._db.count_memories(mt.value, entity_key)
            stats[mt.value] = entry
        stats["embeddings"] = {
            "primary_model": self._embeddings.primary_available,
            "dual_mode": self._embeddings.dual_mode,
            "code_model": self._embeddings.code_available,
        }
        return stats
