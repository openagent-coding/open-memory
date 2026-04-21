# Open Memory Hooks

Hook scripts for integrating Open Memory with Claude Code and Cursor.

## Setup

### 1. Start the server

```bash
# Docker Compose (recommended)
docker compose up -d

# Or locally (requires PostgreSQL with pgvector)
pip install -e .
python -m src.server
```

### 2. Claude Code Integration

**Option A: MCP via stdio (direct process)**

Add to `~/.claude/settings.json` or `.claude/settings.json`:

```json
{
  "mcpServers": {
    "open-memory": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/open-memory",
      "env": {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "open_memory",
        "DB_USER": "memory_user",
        "DB_PASSWORD": "changeme",
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

**Option B: MCP via HTTP (Docker Compose running)**

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

**Add hooks** to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [{
          "type": "command",
          "command": "/path/to/open-memory/hooks/session_start.sh",
          "timeout": 15
        }]
      }
    ],
    "Stop": [
      {
        "hooks": [{
          "type": "command",
          "command": "python3 /path/to/open-memory/hooks/session_stop.py",
          "timeout": 10
        }]
      }
    ]
  }
}
```

### 3. Cursor Integration

**MCP Server**: Add in Cursor Settings > MCP:

- Name: `open-memory`
- URL: `http://localhost:8080/mcp`

**Hooks**: Create `.cursor/hooks.json` in your project:

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "command": "/path/to/open-memory/hooks/session_start.sh",
        "timeout": 15
      }
    ],
    "stop": [
      {
        "command": "python3 /path/to/open-memory/hooks/session_stop.py",
        "timeout": 10
      }
    ]
  }
}
```

## Environment Variables

Set `OPEN_MEMORY_URL` to point hooks at your server:

```bash
export OPEN_MEMORY_URL=http://localhost:8080
```

## Hook Descriptions

| Hook | Event | Purpose |
|------|-------|---------|
| `session_start.sh` | SessionStart | Loads user/project/guidelines memory into agent context |
| `session_stop.py` | Stop | Reminds agent to save important learnings |
| `post_tool_use.py` | PostToolUse | Tracks tool usage patterns |
