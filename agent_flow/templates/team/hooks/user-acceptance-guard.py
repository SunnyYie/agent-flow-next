#!/usr/bin/env python3
"""
AgentFlow User Acceptance Guard — UserPromptSubmit hook

For Medium/Complex tasks, enforce user acceptance before push.

Logic:
  - Read current_phase.md
  - If complexity >= medium and no .user-acceptance-done marker exists,
    remind about user acceptance

Output: <system-reminder> block with acceptance reminder.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_project_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists() or (parent / ".dev-workflow").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _read_current_phase(project_root: Path) -> str:
    """Read current_phase.md content."""
    for state_dir in [".agent-flow/state", ".dev-workflow/state"]:
        phase_path = project_root / state_dir / "current_phase.md"
        if phase_path.is_file():
            try:
                return phase_path.read_text(encoding="utf-8")
            except OSError:
                pass
    return ""


def _get_complexity_level(project_root: Path) -> str:
    """Read complexity level from .complexity-level file."""
    for state_dir in [".agent-flow/state", ".dev-workflow/state"]:
        path = project_root / state_dir / ".complexity-level"
        if path.is_file():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("level="):
                        level = stripped.split("=", 1)[1].strip().lower()
                        if level in ("simple", "medium", "complex"):
                            return level
            except OSError:
                pass
    return "medium"


def _get_complexity_from_phase(phase_content: str) -> str:
    """Extract complexity from current_phase.md as fallback."""
    for line in phase_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- level:"):
            level = stripped.split(":", 1)[1].strip().lower()
            if level in ("simple", "medium", "complex"):
                return level
    return ""


def _has_user_acceptance_marker(project_root: Path) -> bool:
    """Check if .user-acceptance-done marker exists with valid content."""
    for state_dir in [".agent-flow/state", ".dev-workflow/state"]:
        marker_path = project_root / state_dir / ".user-acceptance-done"
        if marker_path.is_file():
            try:
                content = marker_path.read_text(encoding="utf-8").strip()
                if not content:
                    continue
                # Check for structured marker entries
                # Each entry should have at least phase= and status=accepted
                has_accepted = False
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if "status=accepted" in stripped:
                        # Verify required fields exist somewhere in the content
                        has_accepted = True
                        break
                    if stripped.startswith("status:") and "accepted" in stripped:
                        has_accepted = True
                        break
                if has_accepted:
                    return True
                # If any non-empty content exists, treat as accepted (legacy format)
                if content:
                    return True
            except OSError:
                pass
    return False


def _is_past_implement_phase(phase_content: str) -> bool:
    """Check if we're past the IMPLEMENT phase (meaning acceptance should happen)."""
    content_lower = phase_content.lower()

    # Check if IMPLEMENT is completed
    for line in phase_content.splitlines():
        stripped = line.strip()
        if "- implement:" in stripped.lower() and "completed" in stripped.lower():
            return True

    # Check if we're in VERIFY or REFLECT phase
    for line in phase_content.splitlines():
        stripped = line.strip().lower()
        if stripped.startswith("- ") and ":" in stripped:
            parts = stripped[2:].split(":", 1)
            if len(parts) == 2:
                phase_name = parts[0].strip()
                phase_status = parts[1].strip()
                if phase_name in ("verify", "reflect") and phase_status in (
                    "pending", "in_progress", "current", "completed"
                ):
                    return True

    # Check for 验收 keywords
    if "验收" in phase_content or "⚠️双验收" in phase_content:
        return True

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

    # Get complexity
    complexity = _get_complexity_level(project_root)
    if complexity == "simple":
        # Also check phase content directly
        phase_complexity = _get_complexity_from_phase(phase_content)
        if phase_complexity:
            complexity = phase_complexity
        else:
            return  # Simple tasks don't require formal user acceptance

    if complexity == "simple":
        return

    # Check if we're past IMPLEMENT phase (acceptance should have happened by now)
    past_implement = _is_past_implement_phase(phase_content)
    if not past_implement:
        return

    # Check if user acceptance marker exists
    if _has_user_acceptance_marker(project_root):
        return

    # No acceptance marker — output reminder
    if complexity == "complex":
        print(
            "<system-reminder>\n"
            "[AgentFlow ACCEPTANCE] COMPLEX task requires user acceptance!\n\n"
            "No .user-acceptance-done marker found. Complex tasks require user "
            "acceptance before proceeding to push/MR creation.\n\n"
            "Required acceptance for Complex tasks:\n"
            "  - Research phase acceptance\n"
            "  - Plan phase acceptance\n"
            "  - Implement phase acceptance (with test results)\n\n"
            "To complete acceptance:\n"
            "  1. Present a summary of changes and test results to the user\n"
            "  2. Explicitly describe the impact scope and rollback plan\n"
            "  3. Get the user's explicit confirmation (e.g., 'looks good', 'accepted')\n"
            "  4. Write the marker: .agent-flow/state/.user-acceptance-done\n"
            "     Each entry must include:\n"
            "     phase=research|plan|implement\n"
            "     status=accepted\n"
            "     timestamp=ISO8601\n"
            "     task=current task\n"
            "     confirmed_by=user\n"
            "     summary=user's confirmation summary\n\n"
            "DO NOT create the acceptance marker without actual user confirmation.\n"
            "</system-reminder>"
        )
    else:
        # Medium complexity
        print(
            "<system-reminder>\n"
            "[AgentFlow ACCEPTANCE] MEDIUM task requires user acceptance.\n\n"
            "No .user-acceptance-done marker found. Medium tasks should get user "
            "acceptance before pushing code or creating MRs.\n\n"
            "To complete acceptance:\n"
            "  1. Present the change summary to the user\n"
            "  2. Get explicit confirmation\n"
            "  3. Write marker: .agent-flow/state/.user-acceptance-done\n"
            "     (phase=implement, status=accepted, timestamp=..., confirmed_by=user)\n"
            "</system-reminder>"
        )


if __name__ == "__main__":
    main()
