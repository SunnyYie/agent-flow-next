#!/usr/bin/env python3
"""Inject high-confidence memory entries before context compression.

Fires on PreToolUse events.  Only acts when the session has been active
long enough (startup-context.md mtime > 5 minutes, or hook_telemetry
count > 5).  Calls fire_pre_compress() to retrieve high-confidence
entries and injects a compact <system-reminder> with must-survive memory.
"""

from __future__ import annotations

import json
import os
import time
import sys
from pathlib import Path


# Minimum session age (seconds) before we consider injecting memory.
_MIN_SESSION_AGE = 300  # 5 minutes

# Minimum telemetry event count before we consider injecting memory.
_MIN_TELEMETRY_COUNT = 5

# Token budget for the injected reminder (approximate).
_MAX_REMINDER_TOKENS = 500


def _find_project_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists() or (parent / ".dev-workflow").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _session_old_enough(project_root: Path) -> bool:
    """Check if the session has been active long enough to warrant injection.

    Uses a dedicated session-birth-time file (written once at SessionStart)
    as the primary signal.  Falls back to startup-context.md mtime and
    telemetry line count only when the birth-time file is absent (legacy).
    """
    # Primary: dedicated session birth time (clean — written once per session)
    birth_time_path = project_root / ".agent-flow" / "state" / "session-birth-time"
    if birth_time_path.is_file():
        try:
            birth_time = float(birth_time_path.read_text(encoding="utf-8").strip())
            if (time.time() - birth_time) > _MIN_SESSION_AGE:
                return True
            # Session exists but not old enough — skip fallbacks
            return False
        except (ValueError, OSError):
            pass

    # Fallback 1 (legacy): startup-context.md mtime
    try:
        from agent_flow.core.runtime_context import runtime_context_state_path

        startup_ctx = runtime_context_state_path(project_root, target="claude-hook")
    except (ImportError, Exception):
        startup_ctx = None

    if startup_ctx and startup_ctx.is_file():
        try:
            mtime = startup_ctx.stat().st_mtime
            if (time.time() - mtime) > _MIN_SESSION_AGE:
                return True
        except OSError:
            pass

    # Fallback 2 (legacy): hook_telemetry.jsonl line count
    telemetry_path = project_root / ".agent-flow" / "logs" / "hook_telemetry.jsonl"
    if telemetry_path.is_file():
        try:
            count = 0
            with open(telemetry_path, encoding="utf-8") as f:
                for _ in f:
                    count += 1
            if count > _MIN_TELEMETRY_COUNT:
                return True
        except OSError:
            pass

    return False


def _format_entries(entries: list[dict], max_tokens: int = _MAX_REMINDER_TOKENS) -> str:
    """Format high-confidence entries into a compact reminder string.

    Each entry is rendered as one line.  Entries are truncated if the
    total would exceed the approximate token budget (roughly 4 chars/token).
    """
    if not entries:
        return ""

    max_chars = max_tokens * 4
    lines: list[str] = []
    total_chars = 0

    for entry in entries:
        # Build a compact one-line summary
        module = entry.get("module", "")
        exp_type = entry.get("exp_type", entry.get("type", ""))
        description = entry.get("description", "")
        confidence = entry.get("confidence", 0.0)
        abstraction = entry.get("abstraction", "")

        parts = []
        if module:
            parts.append(f"[{module}]")
        if exp_type:
            parts.append(f"({exp_type})")
        if abstraction:
            parts.append(f"<{abstraction}>")
        parts.append(description)
        parts.append(f"(conf:{confidence:.1f})")

        line = " ".join(parts)
        line_len = len(line) + 1  # +1 for newline

        if total_chars + line_len > max_chars:
            break

        lines.append(line)
        total_chars += line_len

    return "\n".join(lines)


def main() -> None:
    started_at = time.monotonic()
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    project_root = _find_project_root()
    if project_root is None or not (project_root / ".agent-flow").exists():
        return

    try:
        from agent_flow.core.hook_telemetry import append_hook_telemetry
    except ImportError:
        return

    # Only act on PreToolUse events
    event_name = payload.get("hook_event_name", "")
    if event_name != "PreToolUse":
        append_hook_telemetry(
            project_root,
            hook_name="pre-compress-guard",
            status="skipped",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={"event_name": str(event_name), "skip_reason": "unsupported-event", "injection_bytes": 0},
        )
        return

    # Only inject if the session has been active long enough
    if not _session_old_enough(project_root):
        append_hook_telemetry(
            project_root,
            hook_name="pre-compress-guard",
            status="skipped",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={"event_name": str(event_name), "skip_reason": "session-not-old-enough", "injection_bytes": 0},
        )
        return

    try:
        from agent_flow.core.lifecycle import fire_pre_compress

        entries = fire_pre_compress(
            project_root,
            metadata={"source": "claude-precompress-hook"},
        )
    except Exception as exc:
        append_hook_telemetry(
            project_root,
            hook_name="pre-compress-guard",
            status="error",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={"event_name": str(event_name), "error": str(exc)},
        )
        return

    if not entries:
        append_hook_telemetry(
            project_root,
            hook_name="pre-compress-guard",
            status="skipped",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={"event_name": str(event_name), "skip_reason": "no-entries", "injection_bytes": 0},
        )
        return

    body = _format_entries(entries)
    if not body.strip():
        append_hook_telemetry(
            project_root,
            hook_name="pre-compress-guard",
            status="skipped",
            duration_ms=(time.monotonic() - started_at) * 1000,
            details={"event_name": str(event_name), "skip_reason": "empty-body", "injection_bytes": 0},
        )
        return

    reminder = f"<system-reminder>\n[pre-compress-guard]\n{body}\n</system-reminder>"
    append_hook_telemetry(
        project_root,
        hook_name="pre-compress-guard",
        status="success",
        duration_ms=(time.monotonic() - started_at) * 1000,
        details={
            "event_name": str(event_name),
            "entries_count": len(entries),
            "injection_bytes": len(reminder.encode("utf-8")),
        },
    )
    print(reminder)


if __name__ == "__main__":
    main()
