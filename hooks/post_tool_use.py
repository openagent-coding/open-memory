#!/usr/bin/env python3
"""Hook: PostToolUse — track tool patterns for agent memory."""
import json
import os
import sys
from pathlib import Path

STATS_FILE = Path(os.environ.get("OPEN_MEMORY_STATS", "/tmp/open-memory-tool-stats.json"))


def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return json.loads(STATS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"tool_counts": {}, "session_tools": 0}


def save_stats(stats: dict) -> None:
    try:
        STATS_FILE.write_text(json.dumps(stats))
    except OSError:
        pass


def main() -> None:
    payload = {}
    if not sys.stdin.isatty():
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, EOFError):
            pass

    tool_name = payload.get("tool_name", "unknown")

    stats = load_stats()
    stats["tool_counts"][tool_name] = stats["tool_counts"].get(tool_name, 0) + 1
    stats["session_tools"] += 1
    save_stats(stats)


if __name__ == "__main__":
    main()
