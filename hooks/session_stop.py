#!/usr/bin/env python3
"""Hook: Stop — trigger open-memory session end workflow."""
import json
import os
import sys


def main() -> None:
    # Consume stdin to prevent pipe errors (payload not used by this hook)
    if not sys.stdin.isatty():
        try:
            sys.stdin.read()
        except (IOError, EOFError):
            pass

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get(
        "CURSOR_PROJECT_DIR", os.getcwd()
    )
    project_name = os.path.basename(project_dir)
    user_id = os.environ.get("USER", "default")

    message = (
        f"Before ending, follow the open-memory skill 'Session End Workflow':\n"
        f"1. Review this conversation for learnings worth persisting\n"
        f"2. Categorize each as user_memory, project_memory, "
        f"project_guidelines, or agent_memory\n"
        f"3. Save each with save_memory(content, memory_type, entity_key)\n"
        f"   - Project scope: entity_key='{project_name}'\n"
        f"   - User scope: entity_key='{user_id}'\n"
        f"4. If session was long, run memory_stats(entity_key='{project_name}') "
        f"and consolidate if needed\n"
        f"5. Skip saving if nothing new was learned"
    )

    # Print instructions to stderr so they appear in hook output for both platforms
    print(message, file=sys.stderr)

    if os.environ.get("CLAUDE_PROJECT_DIR"):
        json.dump({"continue": True}, sys.stdout)
    else:
        json.dump({"followup_message": message}, sys.stdout)


if __name__ == "__main__":
    main()
