#!/usr/bin/env python3
"""workflow-guard: track search evidence for search-before-execute."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

MARKER = ".agent-flow/state/.plugin-search-done"
VALID_SEARCH_PATH_HINTS = (
    "agent-flow/skills",
    "agent-flow/wiki",
    "dev-workflow/skills",
    "dev-workflow/wiki",
    "Soul",
    "soul",
)
ALWAYS_SEARCH_TOOLS = {"WebSearch", "Skill", "Agent"}


def _find_project_root() -> Path | None:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".agent-flow").exists() or (candidate / ".dev-workflow").exists():
            return candidate
    return None


def _search_target(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Grep":
        return f"{tool_input.get('path','')} {tool_input.get('pattern','')}"
    if tool_name == "Read":
        return str(tool_input.get("file_path", ""))
    if tool_name == "Glob":
        return str(tool_input.get("path", ""))
    return ""


def main() -> None:
    project_root = _find_project_root()
    if project_root is None:
        return

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    is_search = tool_name in ALWAYS_SEARCH_TOOLS
    if not is_search and tool_name in {"Grep", "Read", "Glob"}:
        target = _search_target(tool_name, tool_input)
        is_search = any(hint in target for hint in VALID_SEARCH_PATH_HINTS)

    if not is_search:
        return

    marker_path = project_root / MARKER
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(f"timestamp={int(time.time())}\nstatus=ready\n", encoding="utf-8")


if __name__ == "__main__":
    main()
