from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    USER_MEMORY = "user_memory"
    PROJECT_MEMORY = "project_memory"
    PROJECT_GUIDELINES = "project_guidelines"
    AGENT_MEMORY = "agent_memory"


class MemoryEntry(BaseModel):
    id: str
    memory_type: str
    entity_key: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_type: str = "text"
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_accessed: datetime | None = None
    access_count: int = 0


class SaveMemoryResponse(BaseModel):
    id: str
    action: str
    merged_with_id: str | None = None


class SearchResult(BaseModel):
    entry: MemoryEntry
    similarity: float
