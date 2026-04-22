#!/usr/bin/env python3
"""Inject a compact startup context into Claude Code sessions.

On SessionStart: always inject full context.
On UserPromptSubmit: only inject a DIFF (new/changed entries since last
injection), not the full context again.  This avoids redundant
system-reminders on every prompt within the same session.
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

    prompt = _resolve_prompt(payload)
    if not prompt.strip():
        append_hook_telemetry(
            project_root,
            hook_name="startup-context",
            status="skipped",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={
                "event_name": str(payload.get("hook_event_name", "") or ""),
                "skip_reason": "empty-prompt",
                "injection_bytes": 0,
            },
        )
        return

    event_name = str(payload.get("hook_event_name", "") or "")
    is_session_start = event_name == "SessionStart"

    # Write session birth time once at SessionStart — used by pre-compress-guard
    # as a clean signal for session age (not polluted by other writers).
    if is_session_start:
        _write_session_birth_time(project_root)

    try:
        from agent_flow.core.lifecycle import fire_turn_start
        from agent_flow.core.runtime_context import collect_runtime_context, render_runtime_context

        fire_turn_start(
            project_root,
            phase=event_name,
            metadata={"source": "claude-hook"},
        )
        collect_started_at = time.monotonic()
        context = collect_runtime_context(
            project_root,
            prompt,
            runtime_mode="claude-native",
            event=event_name,
        )
        collect_duration_ms = (time.monotonic() - collect_started_at) * 1000
        # SessionStart always gets full context; UserPromptSubmit gets diff
        diff_mode = not is_session_start
        reminder = render_runtime_context(project_root, context, target="claude-hook", diff_mode=diff_mode)
        append_hook_telemetry(
            project_root,
            hook_name="startup-context",
            status="success" if reminder.strip() else "skipped",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={
                "event_name": event_name,
                "skip_reason": "" if reminder.strip() else "empty-reminder",
                "injection_bytes": len(reminder.encode("utf-8")) if reminder else 0,
                "recommended_skills": len(context.recommended_skills),
                "relevant_memory": len(context.relevant_memory),
                "relevant_recall": len(context.relevant_recall),
                "diff_mode": diff_mode,
                "index_duration_ms": round(collect_duration_ms, 2),
            },
        )
        if reminder.strip():
            print(reminder)
    except Exception as exc:
        append_hook_telemetry(
            project_root,
            hook_name="startup-context",
            status="error",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={
                "event_name": str(payload.get("hook_event_name", "") or ""),
                "error": str(exc),
            },
        )
        return


def _resolve_prompt(payload: dict) -> str:
    prompt = payload.get("prompt", "")
    if isinstance(prompt, str) and prompt.strip():
        return prompt

    event_name = payload.get("hook_event_name", "")
    if event_name == "SessionStart":
        return "session start"

    return ""


def _write_session_birth_time(project_root: Path) -> None:
    """Write session-birth-time once at SessionStart.

    Only writes if the file doesn't exist — subsequent UserPromptSubmit events
    within the same session must NOT overwrite it.
    """
    birth_time_path = project_root / ".agent-flow" / "state" / "session-birth-time"
    if birth_time_path.is_file():
        return  # Already written for this session
    try:
        birth_time_path.parent.mkdir(parents=True, exist_ok=True)
        birth_time_path.write_text(str(time.time()), encoding="utf-8")
    except OSError:
        pass


if __name__ == "__main__":
    main()
