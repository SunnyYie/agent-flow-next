"""Helpers for recording Claude/native hook telemetry."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def append_hook_telemetry(
    project_dir: Path,
    *,
    hook_name: str,
    status: str,
    duration_ms: float,
    details: dict[str, Any] | None = None,
) -> None:
    """Append a structured hook telemetry event to the project log."""
    try:
        log_dir = project_dir / ".agent-flow" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        entry: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "hook": hook_name,
            "status": status,
            "duration_ms": round(duration_ms, 2),
        }
        if details:
            entry.update(details)

        with open(log_dir / "hook_telemetry.jsonl", "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
