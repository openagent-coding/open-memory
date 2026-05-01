---
name: open-memory
description: >
  Persistent memory management for AI coding agents using the open-memory MCP server.
  Provides structured workflows for saving, retrieving, searching, and maintaining
  memories across sessions. Use when: (1) Starting a new session and loading relevant
  context, (2) Ending a session and persisting learnings, (3) Mid-session when
  encountering reusable knowledge worth saving (user preferences, project decisions,
  coding conventions, corrections), (4) Memory housekeeping (consolidation, cleanup,
  stats), (5) Agent needs to search past context for a task, (6) User asks about
  memory, preferences, or past decisions. Triggers on: session start/stop hooks,
  "remember this", "save to memory", "what do you know about", "check memory",
  "search memory", "consolidate", "memory stats", "forget this".
---

# Open Memory

Structured memory management using the open-memory MCP server. Six tools are available:
`save_memory`, `get_memory`, `search_memory`, `delete_memory`, `consolidate_memories`,
`memory_stats`. See [references/tool-reference.md](references/tool-reference.md) for
detailed parameter docs.

## Key Concepts

### Memory Types

| Type | Purpose | Entity Key | TTL |
|------|---------|------------|-----|
| `user_memory` | Role, preferences, expertise, workflow habits | `$USER` or username | Permanent |
| `project_memory` | Goals, tech stack, architecture decisions | Project directory basename | 90 days |
| `project_guidelines` | Coding standards, conventions, patterns | Project directory basename | Permanent |
| `agent_memory` | Learned behaviors, corrections, session patterns | Project basename or `default` | 30 days |

### Entity Key Conventions

- **User scope:** `$USER` environment variable (e.g., `nsingla`)
- **Project scope:** `basename` of the project directory (e.g., `open-memory`, `my-app`)
- **Always provide entity_key explicitly.** The server default is `"default"`, which mixes
  memories across projects/users. Never rely on the default.

### Deduplication

`save_memory` auto-deduplicates at similarity >= 0.85. At >= 0.90 it replaces the old
entry; at 0.85-0.90 it appends with a separator. Do not worry about saving duplicates --
the server handles it. Focus on writing clear, atomic entries.

## Session Start Workflow

When a session starts, the hook provides project name and user ID. Load context in two phases:

### Phase 1: Baseline (always load)

```
get_memory(memory_type="project_guidelines", entity_key=PROJECT_NAME, limit=10)
get_memory(memory_type="user_memory", entity_key=USER_ID, limit=5)
```

These are always relevant regardless of the task.

### Phase 2: Task-aware search

After reading the user's first message, search for relevant context:

```
search_memory(query=<derived from user's request>, entity_key=PROJECT_NAME, limit=5)
```

This surfaces project_memory and agent_memory entries relevant to the current task
instead of dumping everything. Derive the query from keywords in the user's request.

### Guidelines

- Do not regurgitate loaded context to the user unless asked.
- Use loaded context to inform your approach silently.
- If no memories are found, proceed normally -- it is a new project or new topic.

## Mid-Session Workflow

### When to Save

Save when you encounter knowledge that would be valuable in a future session:

- **User states a preference or correction:** "I prefer X", "don't do Y", "we use Z"
- **User reveals a project decision:** Architecture choices, deployment details, team conventions
- **Agent discovers a non-obvious convention:** From code analysis or project structure
- **Agent gets corrected:** Save the correction so the mistake is not repeated
- **User provides domain knowledge:** Business logic, terminology, constraints

### When NOT to Save

- Raw code blocks or file contents (the code is already in the repo)
- Transient task status ("currently debugging X")
- Information already in CLAUDE.md or project documentation
- Conversation snippets without actionable insight

### How to Categorize

Determine the correct `memory_type` before saving:

| Signal | Memory Type | Entity Key |
|--------|-------------|------------|
| "I prefer...", "I like...", personal workflow | `user_memory` | `$USER` |
| Architecture, tech stack, deployment, team info | `project_memory` | Project name |
| "Always use...", naming conventions, test patterns | `project_guidelines` | Project name |
| Agent mistake corrected, effective approach found | `agent_memory` | Project name |

### Content Quality Rules

Write atomic, self-contained entries. Each memory should make sense on its own without
conversation context.

Good: `"This project uses pytest with fixtures in conftest.py. Integration tests go in tests/integration/ and require a running PostgreSQL instance."`

Bad: `"User said to use pytest"` (too terse, missing context)

Bad: `"In our conversation about testing, the user mentioned they prefer pytest over unittest because of fixture support and they also said integration tests should hit a real database..."` (conversation log, not atomic)

### Including Metadata

Add descriptive metadata to aid future search:

```
save_memory(
    content="...",
    memory_type="project_guidelines",
    entity_key="my-project",
    metadata={"topic": "testing", "source": "user_preference"}
)
```

Useful metadata keys: `topic`, `source` (user_stated, discovered, correction), `confidence`.

## Session End Workflow

Before the session ends, reflect on what was learned:

### Step 1: Review the conversation

Scan for these patterns:

| Pattern | Example | Memory Type |
|---------|---------|-------------|
| Correction received | "Actually, we use X not Y" | `agent_memory` |
| Preference revealed | "I prefer single-line imports" | `user_memory` |
| Architecture discovered | "Service A calls Service B via gRPC" | `project_memory` |
| Convention established | "Always add error codes to exceptions" | `project_guidelines` |

### Step 2: Save each learning

Make separate `save_memory` calls for each distinct learning. Do not combine unrelated
learnings into a single entry.

### Step 3: Check stats (long sessions only)

If the session involved many saves or extensive work:

```
memory_stats(entity_key=PROJECT_NAME)
```

If any type is approaching 75% of its cap, run `consolidate_memories` for that type.
See [references/memory-hygiene.md](references/memory-hygiene.md) for cap values and
consolidation details.

### Step 4: Skip if nothing learned

Not every session produces saveable learnings. If nothing new was discovered, do not
force a save.

## Memory Hygiene

### Consolidation

Run when `memory_stats` shows a type at >75% of its cap:

```
consolidate_memories(memory_type="project_memory", entity_key=PROJECT_NAME, threshold=0.80)
```

This merges semantically similar entries to free up space.

### Deletion

Use `delete_memory(memory_id)` only when a specific entry is explicitly wrong or
superseded. Get the ID from a prior `get_memory` or `search_memory` result.

### User requests

- "Clean up memory" / "consolidate" -> Run consolidate on all 4 types for the project
- "Forget X" -> Search for X, confirm with user, delete specific entries
- "What do you know about X" -> `search_memory(query="X")`

For cap values, TTLs, and eviction details, see
[references/memory-hygiene.md](references/memory-hygiene.md).

## Common Patterns

### Pattern 1: User corrects the agent

User: "No, we use Makefile targets not shell scripts for builds"

```
save_memory(
    content="Build system uses Makefile targets, not shell scripts. All build commands are make targets.",
    memory_type="agent_memory",
    entity_key=PROJECT_NAME,
    metadata={"topic": "build_system", "source": "correction"}
)
```

### Pattern 2: Discovering a project convention from code

While reading code, discover that all API handlers follow a specific error handling pattern.

```
save_memory(
    content="API handlers return structured errors: {\"error\": {\"code\": \"...\", \"message\": \"...\"}}. Never return raw exception messages.",
    memory_type="project_guidelines",
    entity_key=PROJECT_NAME,
    metadata={"topic": "error_handling", "source": "discovered"}
)
```

### Pattern 3: Starting work on an unfamiliar area

Before diving into code, search for prior context:

```
search_memory(query="authentication middleware", entity_key=PROJECT_NAME, limit=5)
```

### Pattern 4: User says "remember this" "save to memory"

Determine the appropriate memory_type from context, then save. If unclear, ask the user
which scope (personal preference vs project knowledge).
