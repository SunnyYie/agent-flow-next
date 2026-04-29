#!/usr/bin/env python3
"""
AgentFlow User Acceptance Guard — UserPromptSubmit hook.

For Medium/Complex tasks, enforce user acceptance before push.
"""

from __future__ import annotations

import sys
from pathlib import Path

from contract_utils import find_project_root as _shared_find_project_root

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


def _get_complexity_level(project_root: Path) -> str:
    path = project_root / ".agent-flow" / "state" / ".complexity-level"
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
    for line in phase_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- level:"):
            level = stripped.split(":", 1)[1].strip().lower()
            if level in ("simple", "medium", "complex"):
                return level
    return ""


def _has_user_acceptance_marker(project_root: Path) -> bool:
    marker_path = project_root / ".agent-flow" / "state" / ".user-acceptance-done"
    if not marker_path.is_file():
        return False
    try:
        content = marker_path.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not content:
        return False
    for line in content.splitlines():
        stripped = line.strip()
        if "status=accepted" in stripped:
            return True
        if stripped.startswith("status:") and "accepted" in stripped:
            return True
    return True


def _is_past_implement_phase(phase_content: str) -> bool:
    for line in phase_content.splitlines():
        stripped = line.strip()
        if "- implement:" in stripped.lower() and "completed" in stripped.lower():
            return True

    for line in phase_content.splitlines():
        stripped = line.strip().lower()
        if not (stripped.startswith("- ") and ":" in stripped):
            continue
        phase_name, phase_status = stripped[2:].split(":", 1)
        if phase_name.strip() in ("verify", "reflect") and phase_status.strip() in (
            "pending",
            "in_progress",
            "current",
            "completed",
        ):
            return True

    if "验收" in phase_content or "⚠️双验收" in phase_content:
        return True
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

    complexity = _get_complexity_level(project_root)
    if complexity == "simple":
        phase_complexity = _get_complexity_from_phase(phase_content)
        complexity = phase_complexity or "simple"
    if complexity == "simple":
        return

    if not _is_past_implement_phase(phase_content):
        return
    if _has_user_acceptance_marker(project_root):
        return

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
