#!/usr/bin/env python3
"""
AgentFlow Phase Reminder — PostToolUse hook.
在代码修改后，如果缺少 current_phase.md，提醒执行 pre-flight-check。
"""

from __future__ import annotations

import json
import sys

from contract_utils import find_project_root, read_state_path


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    if input_data.get("tool_name", "") not in ("Write", "Edit"):
        sys.exit(0)

    phase_file = read_state_path(project_root, "current_phase.md")
    if not phase_file.is_file():
        print("[REMINDER] No current_phase.md found. Did you run pre-flight-check?")

    sys.exit(0)


if __name__ == "__main__":
    main()
