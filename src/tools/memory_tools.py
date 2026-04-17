from __future__ import annotations

import json
from typing import Any

from fastmcp import Context, FastMCP

from ..memory.service import MemoryService
from ..schemas import MemoryType

_VALID_TYPES = [t.value for t in MemoryType]
_MAX_LIMIT = 500
_MAX_ENTITY_KEY_LEN = 512


def _get_service(ctx: Context) -> MemoryService:
    return ctx.request_context.lifespan_context["memory_service"]


def _json_response(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _validate_entity_key(key: str) -> str:
    if len(key) > _MAX_ENTITY_KEY_LEN:
        raise ValueError(f"entity_key exceeds max length of {_MAX_ENTITY_KEY_LEN}")
    return key


def _validate_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_LIMIT))


def _validate_memory_type(memory_type: str) -> MemoryType:
    try:
        return MemoryType(memory_type)
    except ValueError:
        raise ValueError(f"Invalid memory_type: {memory_type!r}. Valid: {_VALID_TYPES}")


def register_tools(server: FastMCP) -> None:

    @server.tool(
        name="save_memory",
        description=(
            "Save a memory entry. Automatically deduplicates against existing memories "
            "using semantic similarity.\n\n"
            "memory_type options:\n"
            "- user_memory: user role, preferences, expertise, workflow habits\n"
            "- project_memory: project goals, tech stack, architecture decisions\n"
            "- project_guidelines: coding standards, conventions, patterns\n"
            "- agent_memory: learned behaviors, corrections, session patterns"
        ),
    )
    async def save_memory(
        content: str,
        memory_type: str,
        entity_key: str = "default",
        metadata: dict[str, Any] | None = None,
        ctx: Context = None,
    ) -> str:
        mt = _validate_memory_type(memory_type)
        result = await _get_service(ctx).save_memory(
            mt, _validate_entity_key(entity_key), content, metadata
        )
        return _json_response(result.model_dump())

    @server.tool(
        name="get_memory",
        description=(
            "Retrieve stored memories by type and entity key. "
            "Returns the most recently updated entries.\n\n"
            "memory_type options: user_memory, project_memory, "
            "project_guidelines, agent_memory"
        ),
    )
    async def get_memory(
        memory_type: str,
        entity_key: str = "default",
        limit: int = 10,
        ctx: Context = None,
    ) -> str:
        mt = _validate_memory_type(memory_type)
        entries = await _get_service(ctx).get_memory(
            mt, _validate_entity_key(entity_key), _validate_limit(limit)
        )
        return _json_response([e.model_dump() for e in entries])

    @server.tool(
        name="search_memory",
        description=(
            "Semantic search across memories. Finds relevant entries by meaning, "
            "not just keywords. Optionally filter by memory_type and entity_key. "
            "Searches all types by default."
        ),
    )
    async def search_memory(
        query: str,
        memory_types: list[str] | None = None,
        entity_key: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
        ctx: Context = None,
    ) -> str:
        mt_enums = [_validate_memory_type(t) for t in memory_types] if memory_types else None
        if entity_key:
            entity_key = _validate_entity_key(entity_key)
        results = await _get_service(ctx).search_memory(
            query, mt_enums, entity_key, _validate_limit(limit), min_similarity
        )
        return _json_response([r.model_dump() for r in results])

    @server.tool(
        name="delete_memory",
        description="Delete a specific memory entry by its ID.",
    )
    async def delete_memory(
        memory_id: str,
        ctx: Context = None,
    ) -> str:
        deleted = await _get_service(ctx).delete_memory(memory_id)
        return _json_response({"deleted": deleted, "id": memory_id})

    @server.tool(
        name="consolidate_memories",
        description=(
            "Merge similar memories within a type and entity scope to reduce redundancy. "
            "Groups entries by semantic similarity and merges clusters."
        ),
    )
    async def consolidate_memories(
        memory_type: str,
        entity_key: str,
        threshold: float = 0.80,
        ctx: Context = None,
    ) -> str:
        mt = _validate_memory_type(memory_type)
        count = await _get_service(ctx).consolidate(
            mt, _validate_entity_key(entity_key), threshold
        )
        return _json_response({
            "merged_count": count, "memory_type": memory_type, "entity_key": entity_key,
        })

    @server.tool(
        name="memory_stats",
        description=(
            "Get statistics about stored memories: counts per type, cap limits, "
            "and embedding model status."
        ),
    )
    async def memory_stats(
        entity_key: str | None = None,
        ctx: Context = None,
    ) -> str:
        if entity_key:
            entity_key = _validate_entity_key(entity_key)
        stats = await _get_service(ctx).get_stats(entity_key)
        return _json_response(stats)
