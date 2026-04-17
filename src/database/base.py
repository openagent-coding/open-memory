from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryDatabase(ABC):
    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def insert_memory(
        self,
        memory_type: str,
        entity_key: str,
        content: str,
        metadata: dict[str, Any],
        content_type: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
    ) -> str: ...

    @abstractmethod
    async def update_memory(
        self,
        memory_id: str,
        content: str,
        metadata: dict[str, Any],
        content_type: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
    ) -> None: ...

    @abstractmethod
    async def get_memories(
        self, memory_type: str, entity_key: str, limit: int = 10
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def search_by_embedding(
        self,
        embedding: list[float],
        memory_type: str | None = None,
        entity_key: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def search_by_code_embedding(
        self,
        embedding: list[float],
        memory_type: str | None = None,
        entity_key: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def find_similar(
        self,
        memory_type: str,
        entity_key: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
        threshold: float = 0.85,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    async def touch_memories(self, memory_ids: list[str]) -> None: ...

    @abstractmethod
    async def delete_expired(self, memory_type: str, ttl_days: int) -> int: ...

    @abstractmethod
    async def enforce_cap(self, memory_type: str, entity_key: str, cap: int) -> int: ...

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool: ...

    @abstractmethod
    async def delete_memories_by_entity(self, memory_type: str, entity_key: str) -> int: ...

    @abstractmethod
    async def count_memories(self, memory_type: str, entity_key: str) -> int: ...

    @abstractmethod
    def advisory_lock(self, key: int): ...

    @abstractmethod
    async def update_and_delete_batch(
        self,
        primary_id: str,
        content: str,
        metadata: dict[str, Any],
        content_type: str,
        embedding: list[float] | None,
        code_embedding: list[float] | None,
        delete_ids: list[str],
    ) -> None: ...
