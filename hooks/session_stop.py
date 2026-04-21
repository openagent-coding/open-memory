#!/usr/bin/env python3
"""Hook: Stop — remind agent to persist important learnings."""
import json
import os
import sys


def main() -> None:
    payload = {}
    if not sys.stdin.isatty():
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            pass

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get(
        "CURSOR_PROJECT_DIR", os.getcwd()
    )
    project_name = os.path.basename(project_dir)
    is_claude_code = bool(os.environ.get("CLAUDE_PROJECT_DIR"))

    message = (
        f"Session ending for project '{project_name}'. "
        "If you learned important user preferences, project decisions, "
        "coding patterns, or corrections during this session, "
        "save them using the open-memory MCP tools: "
        "save_user_memory, save_project_memory, save_project_guidelines, "
        "or save_agent_memory."
    )

    if is_claude_code:
        json.dump({"systemMessage": message, "suppressOutput": True}, sys.stdout)
    else:
        json.dump({"followup_message": message}, sys.stdout)


if __name__ == "__main__":
    main()
