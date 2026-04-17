from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import numpy as np
from pgvector.asyncpg import register_vector

from ..config import Settings
from ..schemas import MemoryType
from .base import MemoryDatabase

logger = logging.getLogger(__name__)

TABLE = "memories"
_VALID_TYPES = frozenset(t.value for t in MemoryType)


def _validate_type(memory_type: str) -> str:
    if memory_type not in _VALID_TYPES:
        raise ValueError(f"Invalid memory type: {memory_type!r}. Valid: {sorted(_VALID_TYPES)}")
    return memory_type


class PostgresDatabase(MemoryDatabase):
    def __init__(self, settings: Settings):
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        await register_vector(conn)
        await conn.execute("SET hnsw.ef_search = 100")
        await conn.set_type_codec(
            "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
        )

    async def initialize(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._settings.dsn,
            min_size=self._settings.db_pool_min,
            max_size=self._settings.db_pool_max,
            init=self._init_connection,
        )
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await self._create_table(conn)
        logger.info("Database initialized (single table: %s)", TABLE)

    async def _create_table(self, conn: asyncpg.Connection) -> None:
        emb_dim = self._settings.embedding_dim
        code_dim = self._settings.code_embedding_dim
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                memory_type VARCHAR(50) NOT NULL,
                entity_key VARCHAR(512) NOT NULL,
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{{}}'::jsonb,
                embedding vector({emb_dim}),
                code_embedding vector({code_dim}),
                content_type VARCHAR(10) DEFAULT 'text'
                    CHECK (content_type IN ('text', 'code', 'mixed')),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                last_accessed TIMESTAMPTZ DEFAULT NOW(),
                access_count INTEGER DEFAULT 0
            )
        """)
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{TABLE}_type_entity
            ON {TABLE}(memory_type, entity_key)
        """)
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{TABLE}_type
            ON {TABLE}(memory_type)
        """)
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{TABLE}_embedding
            ON {TABLE} USING hnsw (embedding vector_cosine_ops)
            WHERE embedding IS NOT NULL
        """)
        if self._settings.dual_embedding:
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{TABLE}_code_embedding
                ON {TABLE} USING hnsw (code_embedding vector_cosine_ops)
                WHERE code_embedding IS NOT NULL
            """)
        await conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{TABLE}_accessed
            ON {TABLE}(last_accessed)
        """)

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def advisory_lock(self, key: int) -> AsyncIterator[None]:
        async with self._pool.acquire() as conn:
            await conn.execute("SELECT pg_advisory_lock($1)", key)
            try:
                yield
            finally:
                await conn.execute("SELECT pg_advisory_unlock($1)", key)

    def _record_to_dict(self, record: asyncpg.Record) -> dict[str, Any]:
        d = dict(record)
        d["id"] = str(d["id"])
        d.pop("embedding", None)
        d.pop("code_embedding", None)
        return d

    def _to_vector(self, embedding: list[float] | None) -> np.ndarray | None:
        if embedding is None:
            return None
        return np.array(embedding, dtype=np.float32)

    async def insert_memory(
        self,
        memory_type: str,
        entity_key: str,
        content: str,
        metadata: dict[str, Any],
        content_type: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
    ) -> str:
        _validate_type(memory_type)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO {TABLE}
                    (memory_type, entity_key, content, metadata, content_type,
                     embedding, code_embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                memory_type, entity_key, content, metadata, content_type,
                self._to_vector(embedding), self._to_vector(code_embedding),
            )
            return str(row["id"])

    async def update_memory(
        self,
        memory_id: str,
        content: str,
        metadata: dict[str, Any],
        content_type: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {TABLE}
                SET content = $2, metadata = $3, content_type = $4,
                    embedding = $5, code_embedding = $6,
                    updated_at = NOW(), last_accessed = NOW(),
                    access_count = access_count + 1
                WHERE id = $1::uuid
                """,
                memory_id, content, metadata, content_type,
                self._to_vector(embedding), self._to_vector(code_embedding),
            )

    async def get_memories(
        self, memory_type: str, entity_key: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        _validate_type(memory_type)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, memory_type, entity_key, content, metadata, content_type,
                       created_at, updated_at, last_accessed, access_count
                FROM {TABLE}
                WHERE memory_type = $1 AND entity_key = $2
                ORDER BY updated_at DESC
                LIMIT $3
                """,
                memory_type, entity_key, min(limit, 500),
            )
            return [self._record_to_dict(r) for r in rows]

    async def search_by_embedding(
        self,
        embedding: list[float],
        memory_type: str | None = None,
        entity_key: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[dict[str, Any]]:
        vec = self._to_vector(embedding)
        conditions = ["embedding IS NOT NULL", "1 - (embedding <=> $1) >= $2"]
        params: list[Any] = [vec, min_similarity]
        idx = 3

        if memory_type:
            _validate_type(memory_type)
            conditions.append(f"memory_type = ${idx}")
            params.append(memory_type)
            idx += 1
        if entity_key:
            conditions.append(f"entity_key = ${idx}")
            params.append(entity_key)
            idx += 1

        params.append(min(limit, 500))
        where = " AND ".join(conditions)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, memory_type, entity_key, content, metadata, content_type,
                       created_at, updated_at, last_accessed, access_count,
                       1 - (embedding <=> $1) AS similarity
                FROM {TABLE}
                WHERE {where}
                ORDER BY embedding <=> $1
                LIMIT ${idx}
                """,
                *params,
            )
            return [self._record_to_dict(r) for r in rows]

    async def search_by_code_embedding(
        self,
        embedding: list[float],
        memory_type: str | None = None,
        entity_key: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[dict[str, Any]]:
        vec = self._to_vector(embedding)
        conditions = ["code_embedding IS NOT NULL", "1 - (code_embedding <=> $1) >= $2"]
        params: list[Any] = [vec, min_similarity]
        idx = 3

        if memory_type:
            _validate_type(memory_type)
            conditions.append(f"memory_type = ${idx}")
            params.append(memory_type)
            idx += 1
        if entity_key:
            conditions.append(f"entity_key = ${idx}")
            params.append(entity_key)
            idx += 1

        params.append(min(limit, 500))
        where = " AND ".join(conditions)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, memory_type, entity_key, content, metadata, content_type,
                       created_at, updated_at, last_accessed, access_count,
                       1 - (code_embedding <=> $1) AS similarity
                FROM {TABLE}
                WHERE {where}
                ORDER BY code_embedding <=> $1
                LIMIT ${idx}
                """,
                *params,
            )
            return [self._record_to_dict(r) for r in rows]

    async def find_similar(
        self,
        memory_type: str,
        entity_key: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
        threshold: float = 0.85,
    ) -> list[dict[str, Any]]:
        _validate_type(memory_type)
        seen: dict[str, dict[str, Any]] = {}
        async with self._pool.acquire() as conn:
            if embedding is not None:
                vec = self._to_vector(embedding)
                rows = await conn.fetch(
                    f"""
                    SELECT id, memory_type, entity_key, content, metadata, content_type,
                           created_at, updated_at, last_accessed, access_count,
                           1 - (embedding <=> $1) AS similarity
                    FROM {TABLE}
                    WHERE embedding IS NOT NULL
                      AND memory_type = $2 AND entity_key = $3
                      AND 1 - (embedding <=> $1) >= $4
                    ORDER BY embedding <=> $1
                    LIMIT 5
                    """,
                    vec, memory_type, entity_key, threshold,
                )
                for r in rows:
                    d = self._record_to_dict(r)
                    seen[d["id"]] = d

            if code_embedding is not None:
                vec = self._to_vector(code_embedding)
                rows = await conn.fetch(
                    f"""
                    SELECT id, memory_type, entity_key, content, metadata, content_type,
                           created_at, updated_at, last_accessed, access_count,
                           1 - (code_embedding <=> $1) AS similarity
                    FROM {TABLE}
                    WHERE code_embedding IS NOT NULL
                      AND memory_type = $2 AND entity_key = $3
                      AND 1 - (code_embedding <=> $1) >= $4
                    ORDER BY code_embedding <=> $1
                    LIMIT 5
                    """,
                    vec, memory_type, entity_key, threshold,
                )
                for r in rows:
                    d = self._record_to_dict(r)
                    if d["id"] not in seen or d["similarity"] > seen[d["id"]]["similarity"]:
                        seen[d["id"]] = d

        return list(seen.values())

    async def touch_memories(self, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {TABLE}
                SET last_accessed = NOW(), access_count = access_count + 1
                WHERE id = ANY($1::uuid[])
                """,
                memory_ids,
            )

    async def delete_expired(self, memory_type: str, ttl_days: int) -> int:
        _validate_type(memory_type)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"""
                DELETE FROM {TABLE}
                WHERE memory_type = $1
                  AND created_at < NOW() - INTERVAL '1 day' * $2
                """,
                memory_type, ttl_days,
            )
            count = int(result.split()[-1])
            if count:
                logger.info("Deleted %d expired %s entries", count, memory_type)
            return count

    async def enforce_cap(self, memory_type: str, entity_key: str, cap: int) -> int:
        _validate_type(memory_type)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"""
                WITH ranked AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               ORDER BY (
                                   access_count::float
                                   / GREATEST(EXTRACT(EPOCH FROM NOW() - last_accessed) / 86400.0, 1.0)
                               ) DESC
                           ) AS rn
                    FROM {TABLE}
                    WHERE memory_type = $1 AND entity_key = $2
                )
                DELETE FROM {TABLE}
                WHERE id IN (SELECT id FROM ranked WHERE rn > $3)
                """,
                memory_type, entity_key, cap,
            )
            count = int(result.split()[-1])
            if count:
                logger.info("Evicted %d entries (%s, entity=%s)", count, memory_type, entity_key)
            return count

    async def delete_memory(self, memory_id: str) -> bool:
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {TABLE} WHERE id = $1::uuid", memory_id
            )
            return int(result.split()[-1]) > 0

    async def delete_memories_by_entity(self, memory_type: str, entity_key: str) -> int:
        _validate_type(memory_type)
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {TABLE} WHERE memory_type = $1 AND entity_key = $2",
                memory_type, entity_key,
            )
            return int(result.split()[-1])

    async def count_memories(self, memory_type: str, entity_key: str) -> int:
        _validate_type(memory_type)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT COUNT(*) as cnt FROM {TABLE} WHERE memory_type = $1 AND entity_key = $2",
                memory_type, entity_key,
            )
            return row["cnt"]

    async def update_and_delete_batch(
        self,
        primary_id: str,
        content: str,
        metadata: dict[str, Any],
        content_type: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
        delete_ids: list[str],
    ) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""
                    UPDATE {TABLE}
                    SET content = $2, metadata = $3, content_type = $4,
                        embedding = $5, code_embedding = $6,
                        updated_at = NOW(), last_accessed = NOW()
                    WHERE id = $1::uuid
                    """,
                    primary_id, content, metadata, content_type,
                    self._to_vector(embedding), self._to_vector(code_embedding),
                )
                if delete_ids:
                    await conn.execute(
                        f"DELETE FROM {TABLE} WHERE id = ANY($1::uuid[])",
                        delete_ids,
                    )
