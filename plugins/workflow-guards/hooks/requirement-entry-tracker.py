#!/usr/bin/env python3
"""Track required CLAUDE.md / fewshots reads for requirement-entry mode."""

from __future__ import annotations

import json
import sys
from pathlib import Path

STATE_FILE = ".claude/.requirement-entry-state.json"


def _find_repo_root() -> Path | None:
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _load_state(state_path: Path) -> dict | None:
    if not state_path.is_file():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def main() -> None:
    repo_root = _find_repo_root()
    if repo_root is None:
        return
    state_path = repo_root / STATE_FILE
    state = _load_state(state_path)
    if not state or state.get("status") != "pending":
        return

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    if payload.get("tool_name") != "Read":
        return
    file_path = str(payload.get("tool_input", {}).get("file_path", ""))
    if not file_path:
        return

    changed = False
    if file_path == state.get("claude_md"):
        state["claude_md_read"] = True
        changed = True
    if state.get("fewshots") and file_path == state.get("fewshots"):
        state["fewshots_read"] = True
        changed = True

    if not changed:
        return

    if state.get("claude_md_read") and state.get("fewshots_read"):
        if state.get("agent_flow_ready"):
            state["status"] = "ready"
        else:
            state["status"] = "blocked"

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
