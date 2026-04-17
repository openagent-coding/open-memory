#!/bin/bash
# Hook: SessionStart — load relevant memory context
# Works with both Claude Code ($CLAUDE_PROJECT_DIR) and Cursor ($CURSOR_PROJECT_DIR)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-$(pwd)}}"
PROJECT_NAME=$(basename "$PROJECT_DIR")
USER_ID="${USER:-default}"

MEMORY_SERVER="${OPEN_MEMORY_URL:-http://localhost:8080}"

fetch_memory() {
    local memory_type="$1"
    local entity_key="$2"
    local result
    result=$(curl -sf --max-time 5 \
        "${MEMORY_SERVER}/mcp" \
        -H "Content-Type: application/json" \
        -d "{
            \"jsonrpc\": \"2.0\",
            \"method\": \"tools/call\",
            \"params\": {
                \"name\": \"get_memory\",
                \"arguments\": {
                    \"memory_type\": \"${memory_type}\",
                    \"entity_key\": \"${entity_key}\",
                    \"limit\": 20
                }
            },
            \"id\": 1
        }" 2>/dev/null)

    if [ $? -eq 0 ] && [ -n "$result" ]; then
        echo "$result" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    content = data.get('result', {}).get('content', [])
    for item in content:
        text = item.get('text', '')
        if text and text != '[]':
            entries = json.loads(text)
            for entry in entries:
                print(f\"  - {entry.get('content', '')[:200]}\")
except: pass
" 2>/dev/null
    fi
}

{
    echo "=== Open Memory Context ==="
    echo ""
    echo "## User Memory (${USER_ID})"
    fetch_memory "user_memory" "$USER_ID"
    echo ""
    echo "## Project Memory (${PROJECT_NAME})"
    fetch_memory "project_memory" "$PROJECT_NAME"
    echo ""
    echo "## Project Guidelines (${PROJECT_NAME})"
    fetch_memory "project_guidelines" "$PROJECT_NAME"
    echo ""
    echo "## Agent Memory"
    fetch_memory "agent_memory" "${AGENT_TYPE:-default}"
    echo ""
    echo "=== End Memory Context ==="
} >&2

exit 0
