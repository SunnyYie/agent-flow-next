#!/usr/bin/env python3
"""Track Jira prerequisite doc reading/search evidence.

PostToolUse hook:
- When Jira-related wiki/skill paths are searched or read, write marker
  `.jira-context-ready`.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import find_project_root, write_state_path

MARKER = ".jira-context-ready"
JIRA_HINTS = (
    "jira.md",
    "mai-jira-cli.md",
    "jira-search-to-dev",
    "jira",
)


def _extract_search_target(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Read":
        return str(tool_input.get("file_path", ""))
    if tool_name == "Grep":
        return f"{tool_input.get('path','')} {tool_input.get('pattern','')}"
    if tool_name == "Glob":
        return str(tool_input.get("path", ""))
    return ""


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        return

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    if tool_name not in {"Read", "Grep", "Glob", "Skill"}:
        return

    tool_input = payload.get("tool_input", {})
    target = _extract_search_target(tool_name, tool_input).lower()

    if tool_name == "Skill":
        target += " " + str(tool_input).lower()

    if not any(hint in target for hint in JIRA_HINTS):
        return

    marker_path = write_state_path(project_root, MARKER)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        f"timestamp={int(time.time())}\n"
        "status=ready\n"
        f"source={target[:200]}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
