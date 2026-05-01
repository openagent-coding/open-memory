#!/bin/bash
# Hook: SessionStart — load baseline memory context + instruct agent for task-aware retrieval
# Works with Claude Code ($CLAUDE_PROJECT_DIR) and Cursor ($CURSOR_PROJECT_DIR)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-$(pwd)}}"
PROJECT_NAME=$(basename "$PROJECT_DIR")
USER_ID="${USER:-default}"

MEMORY_SERVER="${OPEN_MEMORY_URL:-http://localhost:8080}"
MCP_ENDPOINT="${MEMORY_SERVER}/mcp"

# Check if jq is available; required for safe JSON construction
if ! command -v jq &>/dev/null; then
    echo "=== Open Memory: jq not found ===" >&2
    echo "  Install jq for session_start hook to work." >&2
    echo "=== End Memory Context ===" >&2
    exit 0
fi

# Initialize MCP session and extract session ID
init_session() {
    local response
    response=$(curl -sf --max-time 4 \
        -D - \
        "$MCP_ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -d '{
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "open-memory-hook", "version": "1.0"}
            },
            "id": 0
        }' 2>/dev/null)

    if [ -z "$response" ]; then
        return 1
    fi

    echo "$response" | grep -i "^mcp-session-id:" | sed 's/^[^:]*: *//;s/\r//' | head -1
}

# Fetch memory via MCP streamable-http, parsing SSE response
fetch_memory() {
    local memory_type="$1"
    local entity_key="$2"
    local limit="${3:-10}"
    local session_id="$4"

    local payload
    payload=$(jq -n \
        --arg mt "$memory_type" \
        --arg ek "$entity_key" \
        --argjson lim "$limit" \
        '{jsonrpc:"2.0", method:"tools/call", params:{name:"get_memory",
          arguments:{memory_type:$mt, entity_key:$ek, limit:$lim}}, id:1}')

    local result
    result=$(curl -sf --max-time 4 \
        "$MCP_ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json, text/event-stream" \
        -H "Mcp-Session-Id: ${session_id}" \
        -d "$payload" 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$result" ]; then
        echo "$result" | python3 -c "
import sys, json
try:
    raw = sys.stdin.read()
    for line in raw.splitlines():
        if line.startswith('data: '):
            data = json.loads(line[6:])
            if 'error' in data:
                msg = data['error'].get('message', 'unknown error')
                print(f'  [server error: {msg}]')
                continue
            content = data.get('result', {}).get('content', [])
            for item in content:
                text = item.get('text', '')
                if text and text != '[]':
                    entries = json.loads(text)
                    for entry in entries:
                        print(f\"  - {entry.get('content', '')[:200]}\")
except (json.JSONDecodeError, KeyError, TypeError, IndexError) as e:
    print(f'  [parse error: {e}]')
" 2>/dev/null
    fi
}

{
    SESSION_ID=$(init_session)

    if [ $? -ne 0 ] || [ -z "$SESSION_ID" ]; then
        echo "=== Open Memory: Server unavailable ==="
        echo ""
        echo "Could not connect to memory server at ${MEMORY_SERVER}."
        echo "Memory context will not be loaded. MCP tools may still work"
        echo "if configured via stdio transport."
        echo ""
        echo "Project: ${PROJECT_NAME} | User: ${USER_ID}"
        echo "=== End Memory Context ==="
    else
        echo "=== Open Memory Context ==="
        echo ""
        echo "## Project Guidelines (${PROJECT_NAME})"
        fetch_memory "project_guidelines" "$PROJECT_NAME" 10 "$SESSION_ID"
        echo ""
        echo "## User Preferences (${USER_ID})"
        fetch_memory "user_memory" "$USER_ID" 5 "$SESSION_ID"
        echo ""
        echo "## Task-Aware Context"
        echo "  Use search_memory with a query derived from the user's request"
        echo "  to load relevant project_memory and agent_memory entries."
        echo "  entity_key for project scope: '${PROJECT_NAME}'"
        echo "  entity_key for user scope: '${USER_ID}'"
        echo ""
        echo "## End-of-Session"
        echo "  Before ending, follow the open-memory skill 'Session End Workflow'"
        echo "  to save learnings with the appropriate memory_type."
        echo "=== End Memory Context ==="
    fi
} >&2

exit 0
