#!/usr/bin/env python3
"""Track clarification questions and require post-question recheck + progress.

PostToolUse hook:
- AskUserQuestion -> set `.clarification-recheck-required` as pending
- Any non-readonly execution / code edit -> resolve pending marker
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import find_project_root, is_readonly_bash, read_state_path, write_state_path

REQUIRED_MARKER = ".clarification-recheck-required"
PENDING_MARKER = ".manual-stop-pending"


def _resolve_pending(project_root) -> None:
    for marker_name in (REQUIRED_MARKER, PENDING_MARKER):
        pending = read_state_path(project_root, marker_name)
        if not pending.is_file():
            continue
        pending.write_text(
            f"timestamp={int(time.time())}\nstatus=resolved\nreason=progress-after-clarification\n",
            encoding="utf-8",
        )


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        return

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name == "AskUserQuestion":
        # Set clarification-recheck-required
        marker = write_state_path(project_root, REQUIRED_MARKER)
        marker.parent.mkdir(parents=True, exist_ok=True)
        question = ""
        if isinstance(tool_input, dict):
            question = str(tool_input.get("question", "")).strip().replace("\n", " ")[:200]
        marker.write_text(
            f"timestamp={int(time.time())}\n"
            "status=pending\n"
            f"question={question or 'unspecified'}\n"
            "reason=post-clarification-recheck-required\n",
            encoding="utf-8",
        )

        # Set manual-stop-pending
        stop_marker = write_state_path(project_root, PENDING_MARKER)
        stop_marker.parent.mkdir(parents=True, exist_ok=True)
        stop_marker.write_text(
            f"timestamp={int(time.time())}\nstatus=pending\nreason=waiting-for-next-gate-or-progress\n",
            encoding="utf-8",
        )
        return

    # Any substantive progress resolves both markers
    if tool_name in {"Write", "Edit", "MultiEdit"}:
        _resolve_pending(project_root)
        return

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if not is_readonly_bash(command):
            _resolve_pending(project_root)


if __name__ == "__main__":
    main()
