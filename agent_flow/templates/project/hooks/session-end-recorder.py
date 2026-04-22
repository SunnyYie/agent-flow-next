#!/usr/bin/env python3
"""Record session-end lifecycle event when Claude Code session closes.

Fired on the SessionEnd Claude Code hook event. Calls fire_session_end()
to record session completion in the observations database.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path


def _find_project_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists() or (parent / ".dev-workflow").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _bootstrap_import_path(project_root: Path) -> None:
    """Ensure ``agent_flow`` package is importable when hooks run from ~/.agent-flow/hooks."""
    candidates = [project_root, *project_root.parents]
    for candidate in candidates:
        if (candidate / "agent_flow").is_dir():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            return


def main() -> None:
    started_at = time.monotonic()
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    project_root = _find_project_root()
    if project_root is None or not (project_root / ".agent-flow").exists():
        return

    _bootstrap_import_path(project_root)
    try:
        from agent_flow.core.hook_telemetry import append_hook_telemetry
    except ImportError:
        return

    try:
        from agent_flow.core.lifecycle import fire_session_end

        fire_session_end(
            project_root,
            phase="SessionEnd",
            metadata={"source": "claude-hook"},
        )
        # Clean up session-birth-time so the next session starts fresh
        _cleanup_session_birth_time(project_root)
        append_hook_telemetry(
            project_root,
            hook_name="session-end-recorder",
            status="success",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={"event_name": str(payload.get("hook_event_name", "") or "")},
        )
    except Exception as exc:
        append_hook_telemetry(
            project_root,
            hook_name="session-end-recorder",
            status="error",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={"event_name": str(payload.get("hook_event_name", "") or ""), "error": str(exc)},
        )
        return


if __name__ == "__main__":
    main()


def _cleanup_session_birth_time(project_root: Path) -> None:
    """Remove session-birth-time at session end so the next session starts fresh."""
    birth_time_path = project_root / ".agent-flow" / "state" / "session-birth-time"
    if birth_time_path.is_file():
        try:
            birth_time_path.unlink()
        except OSError:
            pass
