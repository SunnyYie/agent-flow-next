#!/usr/bin/env python3
"""
AgentFlow Self-Questioning Enforcer — UserPromptSubmit hook

After VERIFY phase, enforce self-questioning before REFLECT.
Checks if .self-questioning-done marker exists. If current_phase.md
shows phase REFLECT or later but no marker, prints a warning.

Output: <system-reminder> block with warning message.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


MARKER_FILE = ".agent-flow/state/.self-questioning-done"


def _find_project_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _read_current_phase(project_root: Path) -> str:
    """Read current_phase.md content."""
    phase_path = project_root / ".agent-flow/state" / "current_phase.md"
    if phase_path.is_file():
        try:
            return phase_path.read_text(encoding="utf-8")
        except OSError:
            pass
    return ""


def _get_rpi_phase(phase_content: str) -> str | None:
    """Extract current RPI phase from current_phase.md."""
    for line in phase_content.splitlines():
        stripped = line.strip()
        # Match lines like "- Research: completed" or "- Implement: pending"
        if stripped.startswith("- ") and ":" in stripped:
            parts = stripped[2:].split(":", 1)
            phase_name = parts[0].strip().lower()
            phase_status = parts[1].strip().lower()
            if phase_status in ("in_progress", "current"):
                return phase_name
    # Fallback: check if any phase is marked as pending (meaning we're at that phase)
    # Also check for explicit phase markers
    content_lower = phase_content.lower()
    if "reflect" in content_lower and "completed" not in content_lower.split("reflect")[0][-50:]:
        # Check if REFLECT is the current phase in RPI section
        for line in phase_content.splitlines():
            stripped = line.strip().lower()
            if "- reflect" in stripped and ("pending" in stripped or "in_progress" in stripped or "current" in stripped):
                return "reflect"
    return None


def _is_at_or_past_reflect(phase_content: str) -> bool:
    """Check if current phase is REFLECT or later."""
    content_lower = phase_content.lower()

    # Check RPI section for REFLECT being pending/in_progress
    rpi_section = False
    for line in phase_content.splitlines():
        stripped = line.strip()
        if "RPI" in stripped and "阶段" in stripped:
            rpi_section = True
            continue
        if rpi_section and stripped.startswith("- "):
            phase_name = stripped[2:].split(":")[0].strip().lower()
            phase_status = stripped.split(":", 1)[1].strip().lower() if ":" in stripped else ""

            # If REFLECT is pending or in_progress, we're at or past it
            if phase_name == "reflect" and phase_status in ("pending", "in_progress", "current"):
                return True

            # If a phase after REFLECT is active (there isn't one normally, but just in case)
            if phase_name in ("evolve",) and phase_status in ("pending", "in_progress", "current"):
                return True

    # Fallback: check if VERIFY is completed and REFLECT is mentioned
    verify_completed = False
    reflect_pending = False
    for line in phase_content.splitlines():
        stripped = line.strip().lower()
        if "verify" in stripped and "completed" in stripped:
            verify_completed = True
        if "reflect" in stripped and ("pending" in stripped or "in_progress" in stripped):
            reflect_pending = True

    if verify_completed and reflect_pending:
        return True

    return False


def _has_self_questioning_marker(project_root: Path) -> bool:
    """Check if .self-questioning-done marker exists."""
    marker_path = project_root / MARKER_FILE
    if marker_path.is_file():
        try:
            content = marker_path.read_text(encoding="utf-8").strip()
            return bool(content)
        except OSError:
            pass
    return False


def main() -> None:
    try:
        # Read stdin (UserPromptSubmit provides prompt info, but we ignore it)
        _ = sys.stdin.read()
    except Exception:
        pass

    project_root = _find_project_root()
    if project_root is None:
        return

    # Read current_phase.md
    phase_content = _read_current_phase(project_root)
    if not phase_content:
        return

    # Check if we're at or past REFLECT phase
    if not _is_at_or_past_reflect(phase_content):
        return

    # Check if self-questioning marker exists
    if _has_self_questioning_marker(project_root):
        return

    # No marker found — output warning as <system-reminder>
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
