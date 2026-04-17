from __future__ import annotations

import logging
from typing import Any

import numpy as np

from ..config import Settings
from ..database.base import MemoryDatabase
from ..embeddings.manager import EmbeddingManager

logger = logging.getLogger(__name__)


class ConsolidationService:
    def __init__(
        self, db: MemoryDatabase, embeddings: EmbeddingManager, settings: Settings
    ):
        self._db = db
        self._embeddings = embeddings
        self._settings = settings

    async def consolidate(
        self, memory_type: str, entity_key: str, threshold: float = 0.80
    ) -> int:
        entries = await self._db.get_memories(memory_type, entity_key, limit=1000)
        if len(entries) < 2:
            return 0

        embeddings_cache: dict[str, tuple[list[float] | None, list[float] | None]] = {}
        for entry in entries:
            emb, code_emb = await self._embeddings.embed(entry["content"])
            embeddings_cache[entry["id"]] = (emb, code_emb)

        merged_ids: set[str] = set()
        merge_count = 0

        for i, entry_a in enumerate(entries):
            if entry_a["id"] in merged_ids:
                continue
            emb_a, code_a = embeddings_cache[entry_a["id"]]
            cluster: list[dict[str, Any]] = [entry_a]

            for entry_b in entries[i + 1 :]:
                if entry_b["id"] in merged_ids:
                    continue
                similarity = _compute_similarity(
                    emb_a, code_a, *embeddings_cache[entry_b["id"]]
                )
                if similarity >= threshold:
                    cluster.append(entry_b)
                    merged_ids.add(entry_b["id"])

            if len(cluster) > 1:
                await self._merge_cluster(cluster)
                merge_count += len(cluster) - 1

        if merge_count:
            logger.info(
                "Consolidated %d entries (%s, entity=%s)",
                merge_count, memory_type, entity_key,
            )
        return merge_count

    async def _merge_cluster(self, cluster: list[dict[str, Any]]) -> None:
        primary = cluster[0]
        merged_content = "\n\n".join(e["content"] for e in cluster)

        merged_metadata: dict[str, Any] = {}
        for entry in cluster:
            merged_metadata.update(entry.get("metadata") or {})
        merged_metadata["consolidated_from"] = [e["id"] for e in cluster]

        emb, code_emb = await self._embeddings.embed(merged_content)

        await self._db.update_and_delete_batch(
            primary_id=primary["id"],
            content=merged_content,
            metadata=merged_metadata,
            content_type=primary.get("content_type", "text"),
            embedding=emb,
            code_embedding=code_emb,
            delete_ids=[e["id"] for e in cluster[1:]],
        )


def _compute_similarity(
    emb_a: list[float] | None,
    code_a: list[float] | None,
    emb_b: list[float] | None,
    code_b: list[float] | None,
) -> float:
    similarities: list[float] = []
    if emb_a and emb_b:
        a, b = np.array(emb_a), np.array(emb_b)
        similarities.append(float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))))
    if code_a and code_b:
        a, b = np.array(code_a), np.array(code_b)
        similarities.append(float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))))
    return max(similarities) if similarities else 0.0
