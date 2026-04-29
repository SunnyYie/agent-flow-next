#!/usr/bin/env python3
"""
AgentFlow Self-Questioning Enforcer — UserPromptSubmit hook.

After VERIFY phase, enforce self-questioning before REFLECT.
Checks if .self-questioning-done marker exists. If current_phase.md
shows phase REFLECT or later but no marker, prints a warning.
"""

from __future__ import annotations

import sys
from pathlib import Path

from contract_utils import find_project_root as _shared_find_project_root

MARKER_FILE = ".agent-flow/state/.self-questioning-done"


def _find_project_root() -> Path | None:
    return _shared_find_project_root()


def _read_current_phase(project_root: Path) -> str:
    phase_path = project_root / ".agent-flow" / "state" / "current_phase.md"
    if phase_path.is_file():
        try:
            return phase_path.read_text(encoding="utf-8")
        except OSError:
            pass
    return ""


def _is_at_or_past_reflect(phase_content: str) -> bool:
    rpi_section = False
    for line in phase_content.splitlines():
        stripped = line.strip()
        if "RPI" in stripped and "阶段" in stripped:
            rpi_section = True
            continue
        if rpi_section and stripped.startswith("- "):
            phase_name = stripped[2:].split(":")[0].strip().lower()
            phase_status = stripped.split(":", 1)[1].strip().lower() if ":" in stripped else ""
            if phase_name == "reflect" and phase_status in ("pending", "in_progress", "current"):
                return True
            if phase_name in ("evolve",) and phase_status in ("pending", "in_progress", "current"):
                return True

    verify_completed = False
    reflect_pending = False
    for line in phase_content.splitlines():
        stripped = line.strip().lower()
        if "verify" in stripped and "completed" in stripped:
            verify_completed = True
        if "reflect" in stripped and ("pending" in stripped or "in_progress" in stripped):
            reflect_pending = True
    return verify_completed and reflect_pending


def _has_self_questioning_marker(project_root: Path) -> bool:
    marker_path = project_root / MARKER_FILE
    if marker_path.is_file():
        try:
            if marker_path.read_text(encoding="utf-8").strip():
                return True
        except OSError:
            pass
    return False


def main() -> None:
    try:
        _ = sys.stdin.read()
    except Exception:
        pass

    project_root = _find_project_root()
    if project_root is None:
        return

    phase_content = _read_current_phase(project_root)
    if not phase_content:
        return
    if not _is_at_or_past_reflect(phase_content):
        return
    if _has_self_questioning_marker(project_root):
        return

    print(
        "<system-reminder>\n"
        "[AgentFlow WARNING] Self-questioning not completed before REFLECT phase!\n\n"
        "The current task has entered REFLECT phase but the self-questioning check "
        "has not been performed. Per the AgentFlow iron laws, after VERIFY and "
        "before REFLECT, you must execute the self-questioning skill.\n\n"
        "Steps:\n"
        "  1. Read ~/.agent-flow/skills/workflow/self-questioning/handler.md\n"
        "  2. Execute the 10-item structured self-check (process compliance, "
        "knowledge utilization, efficiency analysis, knowledge gaps)\n"
        "  3. Write the self-questioning report to "
        ".agent-flow/state/self-questioning-report.md\n"
        "  4. Create marker: write to .agent-flow/state/.self-questioning-done\n"
        "  5. Then proceed with REFLECT (writing to Soul.md etc.)\n"
        "</system-reminder>"
    )


if __name__ == "__main__":
    main()
