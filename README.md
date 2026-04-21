# Open Memory

Give your AI coding agent a persistent memory so you never repeat yourself.

## The Problem

Every time you start a conversation with Claude Code, Cursor, or any AI coding agent, it starts from zero. It doesn't know:

- That you're a senior backend engineer who prefers Go
- That this project uses dependency injection and follows hexagonal architecture
- That the team convention is `snake_case` for Python and the PR template lives in `.github/`
- That last week it tried a migration approach that broke staging, and you told it never to do that again

So you repeat the same context, the same preferences, the same corrections — every single session. CLAUDE.md/AGENTS.md and `.cursorrules` files help, but they're static, manual, and don't learn from your interactions.

## What Open Memory Does

Open Memory is a **memory layer** for AI coding agents. It runs as an [MCP server](https://modelcontextprotocol.io/) that your agent connects to — and then your agent can **store and retrieve context automatically**, across sessions, across projects.

**The workflow:**

```
You type a prompt
        ↓
Agent auto-fetches from Open Memory:
  → your preferences (user_memory)
  → project context and decisions (project_memory)
  → coding standards and conventions (project_guidelines)
  → what it learned in past sessions (agent_memory)
        ↓
Agent has full context before writing a single line of code
        ↓
Agent works on your task
        ↓
At session end, agent saves anything new it learned
  → "user prefers functional patterns over OOP"
  → "this project uses sqlc, not GORM"
  → "never run migrations without a backup"
        ↓
Next session starts with all of that already loaded
```

**What this means in practice:**

- You say "fix the auth bug" — the agent already knows your auth uses JWT with Redis session store, your error handling pattern, and your test conventions. It doesn't ask you to explain your stack.
- You switch to a different project — the agent loads *that* project's guidelines and conventions instead. No manual context switching.
- You correct the agent once ("don't use mocks for database tests, we got burned last quarter") — it remembers across every future session.
- A teammate uses the same project? They get the shared project guidelines but their own user preferences.

## How It Works Under the Hood

Open Memory stores memories in PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) for semantic search. When your agent needs context, it doesn't do keyword matching — it searches by *meaning*. Asking "how do we handle errors?" finds the memory about the `Result<T,E>` pattern even though the words don't overlap.

**Memory types** with different lifetimes:

| Type | What goes in it | TTL | Example |
|------|----------------|-----|---------|
| `user_memory` | Your role, preferences, expertise | Permanent | "Senior Go dev, prefers table-driven tests" |
| `project_memory` | Project-specific context and decisions | 90 days | "Migrating from monolith to microservices, using gRPC" |
| `project_guidelines` | Coding standards, conventions | Permanent | "All errors must be wrapped with `fmt.Errorf`" |
| `agent_memory` | Agent-learned behaviors, corrections | 30 days | "User rejected mock-based DB tests, use testcontainers" |

**Built-in bloat control:**
- **Dedup-on-write** — saves "user prefers dark mode" once, not 50 times. Before inserting, checks semantic similarity against existing entries. If > 85% similar, merges instead of duplicating.
- **Access-frequency eviction** — entries that are never retrieved get evicted first when approaching the cap.
- **Consolidation** — merge related memories into concise summaries on demand.
- **TTL** — session-level memories (agent_memory) auto-expire after 30 days.

**Zero LLM calls for retrieval.** Two lightweight embedding models run locally (~500MB combined, no API calls, no cost). Nomic Embed Text v1.5 handles natural language, CodeRankEmbed-137M handles code. When the agent searches memory, it's a vector similarity query in PostgreSQL — not an LLM round-trip. Fast and free.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and data flow.

## Quick Start

```bash
# 1. Clone and start
git clone <repo-url> && cd open-memory
cp .env.example .env  # edit DB_PASSWORD at minimum

# 2. Run with Docker Compose
docker compose up -d

# 3. Connect your agent (see Integration below)
```

### Local Development (without Docker)

```bash
# Requires PostgreSQL with pgvector extension
pip install -e .
python -m src.server
```

## Integration

### Claude Code

**Option A: stdio (Docker, single container)**

Build once, then point Claude Code at it. PostgreSQL + pgvector run inside the container — no external database needed.

```bash
docker build -t open-memory .
```

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "open-memory": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "open-memory"],
      "env": {}
    }
  }
}
```

To override defaults from `.env.example`, pass `-e` flags:

```json
{
  "mcpServers": {
    "open-memory": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "DB_PASSWORD=secret",
        "open-memory"
      ],
      "env": {}
    }
  }
}
```

To persist data across container restarts, mount a volume for PostgreSQL:

```json
{
  "mcpServers": {
    "open-memory": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "open-memory-pgdata:/var/lib/postgresql",
        "open-memory"
      ],
      "env": {}
    }
  }
}
```

**Option B: HTTP (Docker Compose running)**

```json
{
  "mcpServers": {
    "open-memory": {
      "type": "http",
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

### Cursor

Add in Cursor Settings > MCP Servers:

- **Name:** `open-memory`
- **URL:** `http://localhost:8080/mcp`

### Hooks (recommended)

Hooks make the memory automatic — load context at session start, prompt to save at session end. Without hooks, the agent can still use the MCP tools manually, but you'll need to ask it to "check memory" yourself.

See [hooks/README.md](hooks/README.md) for Claude Code and Cursor setup.

## MCP Tools

6 tools — the agent uses these automatically once connected:

| Tool | Description |
|------|-------------|
| `save_memory` | Save a memory (user, project, guidelines, or agent) |
| `get_memory` | Retrieve memories by type and entity |
| `search_memory` | Semantic search across all memory types |
| `delete_memory` | Remove a specific memory |
| `consolidate_memories` | Merge similar entries to reduce redundancy |
| `memory_stats` | View counts, caps, and model status |

## Configuration

All settings via environment variables. See [.env.example](.env.example) for the full list.

### Embedding Models

Default: dual models on CPU (~500MB combined):
- **Text:** Nomic Embed Text v1.5 @ 256d (Matryoshka) — 137M params, 8192 token context, 100+ languages
- **Code:** CodeRankEmbed-137M @ 768d — beats Voyage Code 3 on CodeSearchNet

Swap via env vars:

```bash
# Use different text model
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5 EMBEDDING_DIM=768

# Use different code model
CODE_EMBEDDING_MODEL=jinaai/jina-code-v2 CODE_EMBEDDING_DIM=768

# Single model mode (disable code-specific model)
DUAL_EMBEDDING=false EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B EMBEDDING_DIM=256
```

### GPU Support

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### Kubernetes

```bash
kubectl apply -f k8s/
```

## How is this different from CLAUDE.md/AGENTS.md / .cursorrules?

| | CLAUDE.md/AGENTS.md / .cursorrules | Open Memory |
|---|---|---|
| **Updates** | Manual — you edit a file | Automatic — agent saves what it learns |
| **Scope** | Per-project, static | Per-user + per-project + per-agent, dynamic |
| **Search** | Agent reads the whole file every time | Semantic search — agent fetches only relevant memories |
| **Dedup** | You manage duplicates | Automatic deduplication |
| **Cross-project** | Doesn't carry over | User preferences follow you across all projects |
| **Learning** | Doesn't learn from corrections | Agent saves corrections as agent_memory |

Open Memory doesn't replace CLAUDE.md/AGENTS.md — it complements them. Those files are great for static, well-defined project instructions. Open Memory handles the dynamic, accumulated, cross-session context that static files can't.

## Development

```bash
pip install -e ".[dev]"
pytest -v
```

## License

Apache 2.0
