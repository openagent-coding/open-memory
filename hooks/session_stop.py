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
    user_id = os.environ.get("USER", "default")

    if os.environ.get("CLAUDE_PROJECT_DIR"):
        json.dump({"continue": True}, sys.stdout)
    else:
        message = (
            f"Session ending for project '{project_name}'. "
            "Save any important learnings using the open-memory MCP tool "
            "'save_memory' with the appropriate memory_type. "
            f"Use entity_key='{project_name}' for project-scoped memories "
            f"or entity_key='{user_id}' for user-scoped memories."
        )
        json.dump({"followup_message": message}, sys.stdout)

if __name__ == "__main__":
    main()
