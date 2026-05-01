# Tool Reference

Detailed parameter documentation for all 6 open-memory MCP tools.

## save_memory

Save a memory entry with automatic semantic deduplication.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | string | yes | - | The memory content to save |
| `memory_type` | string | yes | - | One of: `user_memory`, `project_memory`, `project_guidelines`, `agent_memory` |
| `entity_key` | string | no | `"default"` | Scoping key (max 512 chars). Use `$USER` for user scope, project name for project scope |
| `metadata` | object | no | `{}` | Arbitrary key-value metadata (e.g., `{"topic": "auth", "source": "correction"}`) |

**Returns:** `{"id": "uuid", "action": "inserted"|"merged", "merged_with_id": "uuid"|null}`

**Dedup behavior:**
- Similarity >= 0.90: replaces old content with new content
- Similarity 0.85-0.90: appends new content to old with `---` separator
- Similarity < 0.85: inserts as new entry
- If cap is exceeded after insert, the least-accessed oldest entry is evicted

## get_memory

Retrieve stored memories by type and entity key, sorted by most recently updated.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `memory_type` | string | yes | - | One of the 4 valid types |
| `entity_key` | string | no | `"default"` | Scoping key |
| `limit` | integer | no | `10` | Max entries to return (clamped to 1-500) |

**Returns:** Array of `MemoryEntry` objects, most recently updated first.

## search_memory

Semantic search across memories. Uses dual-mode embedding (text + code) with reciprocal
rank fusion. Searches all types by default.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | yes | - | Natural language search query |
| `memory_types` | string[] | no | all types | Filter to specific types |
| `entity_key` | string | no | all keys | Filter to specific entity scope |
| `limit` | integer | no | `10` | Max results (clamped to 1-500) |
| `min_similarity` | float | no | `0.5` | Minimum similarity threshold (0-1) |

**Returns:** Array of `{"entry": MemoryEntry, "similarity": float}`, sorted by relevance.

**Tips:**
- Use natural language queries, not keywords: "how we handle auth" > "auth"
- Lower `min_similarity` to 0.3 for broader results when few matches are expected
- Omit `entity_key` to search across all projects/users

## delete_memory

Delete a specific memory entry by its UUID.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `memory_id` | string | yes | - | UUID of the entry (from get/search results) |

**Returns:** `{"deleted": true|false, "id": "uuid"}`

## consolidate_memories

Merge semantically similar entries within a type/entity scope to reduce redundancy.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `memory_type` | string | yes | - | Type to consolidate |
| `entity_key` | string | yes | - | Entity scope to consolidate |
| `threshold` | float | no | `0.80` | Similarity threshold for grouping into merge clusters |

**Returns:** `{"merged_count": int, "memory_type": "...", "entity_key": "..."}`

## memory_stats

Get counts per memory type, cap limits, and embedding model status.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `entity_key` | string | no | all keys | Filter stats to a specific entity scope |

**Returns:** Object with per-type counts, caps, and model info.

## MemoryEntry Schema

Fields returned for each memory entry:

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID |
| `memory_type` | string | Type of memory |
| `entity_key` | string | Scoping key |
| `content` | string | The memory content |
| `metadata` | object | Custom metadata |
| `content_type` | string | Always `"text"` |
| `created_at` | datetime | When first created |
| `updated_at` | datetime | Last modified (save/merge) |
| `last_accessed` | datetime | Last retrieved (get/search) |
| `access_count` | integer | Times retrieved |
