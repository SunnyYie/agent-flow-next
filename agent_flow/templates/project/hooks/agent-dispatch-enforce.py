#!/usr/bin/env python3
"""
AgentFlow Agent Dispatch Enforcer — UserPromptSubmit hook

For Medium/Complex tasks, remind about sub-agent delegation.

Logic:
  - Read current_phase.md
  - If complexity >= medium and phase is EXECUTE, print reminder about sub-agent dispatch
  - Check if flow-context.yaml exists and context budget > 70%, print stronger reminder

Output: <system-reminder> block with delegation reminder.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

COMPLEXITY_FILE_NAMES = [".complexity-level"]


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
        for filename in COMPLEXITY_FILE_NAMES:
            path = project_root / state_dir / filename
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
    return "medium"  # Default to medium for safety


def _get_complexity_from_phase(phase_content: str) -> str:
    """Extract complexity from current_phase.md as fallback."""
    for line in phase_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- level:"):
            level = stripped.split(":", 1)[1].strip().lower()
            if level in ("simple", "medium", "complex"):
                return level
    return ""


def _is_execute_phase(phase_content: str) -> bool:
    """Check if current phase is EXECUTE."""
    content_lower = phase_content.lower()

    # Check RPI section
    rpi_section = False
    for line in phase_content.splitlines():
        stripped = line.strip()
        if "RPI" in stripped and ("阶段" in stripped or "phase" in stripped.lower()):
            rpi_section = True
            continue
        if rpi_section and stripped.startswith("- "):
            parts = stripped[2:].split(":", 1)
            if len(parts) == 2:
                phase_name = parts[0].strip().lower()
                phase_status = parts[1].strip().lower()
                if phase_name == "implement" and phase_status in ("pending", "in_progress", "current"):
                    return True
            # If we leave RPI section
            if not stripped.startswith("- ") or (stripped.startswith("- ") and ":" not in stripped[2:]):
                rpi_section = False

    # Fallback: check for EXECUTE keywords in the content
    if "implement:" in content_lower or "implement :" in content_lower:
        for line in phase_content.splitlines():
            stripped = line.strip().lower()
            if "implement" in stripped and any(
                status in stripped for status in ["pending", "in_progress", "current"]
            ):
                return True

    return False


def _read_flow_context_budget(project_root: Path) -> dict:
    """Read budget info from flow-context.yaml using simple parsing."""
    for state_dir in [".agent-flow/state", ".dev-workflow/state"]:
        fc_path = project_root / state_dir / "flow-context.yaml"
        if not fc_path.is_file():
            continue
        try:
            content = fc_path.read_text(encoding="utf-8")
            budget = {}
            in_budget = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("context_budget:"):
                    in_budget = True
                    budget["exists"] = True
                    continue
                if in_budget:
                    if stripped.startswith("used:"):
                        try:
                            budget["used"] = int(stripped.split(":", 1)[1].strip())
                        except ValueError:
                            pass
                    elif stripped.startswith("max:"):
                        try:
                            budget["max"] = int(stripped.split(":", 1)[1].strip())
                        except ValueError:
                            pass
                    elif stripped.startswith("status:"):
                        budget["status"] = stripped.split(":", 1)[1].strip()
                    elif not stripped.startswith(" ") and stripped and not stripped.startswith("#"):
                        in_budget = False
            return budget
        except OSError:
            pass
    return {}


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
    if not complexity or complexity == "simple":
        # Also check phase content directly
        phase_complexity = _get_complexity_from_phase(phase_content)
        if phase_complexity:
            complexity = phase_complexity
        else:
            return  # Simple tasks don't need sub-agent dispatch

    if complexity == "simple":
        return

    # Check agent-team-config.yaml for team mode
    team_mode = ""
    for state_dir in [".agent-flow/state", ".dev-workflow/state"]:
        team_config_path = project_root / state_dir / "agent-team-config.yaml"
        if team_config_path.is_file():
            try:
                import yaml as _yaml
                with open(team_config_path, encoding="utf-8") as f:
                    team_data = _yaml.safe_load(f)
                team_mode = team_data.get("team_mode", "")
            except Exception:
                pass
            break

    # Check if we're in EXECUTE phase
    in_execute = _is_execute_phase(phase_content)
    if not in_execute:
        return

    # Check context budget from flow-context.yaml
    budget = _read_flow_context_budget(project_root)
    budget_status = budget.get("status", "healthy")
    budget_exists = budget.get("exists", False)

    used = budget.get("used", 0)
    max_budget = budget.get("max", 200000)
    pct = used * 100 // max_budget if max_budget > 0 else 0

    # Determine reminder strength
    if budget_status == "critical" or (budget_exists and pct > 70):
        print(
            "<system-reminder>\n"
            "[AgentFlow DISPATCH CRITICAL] Context budget > 70% during EXECUTE phase!\n\n"
            f"Current budget: {used // 1000}K / {max_budget // 1000}K tokens ({pct}%)\n"
            f"Task complexity: {complexity.upper()}\n\n"
            "MANDATORY: All remaining work MUST be delegated to sub-agents.\n"
            "Main agent must only manage state — no direct code writing or file reading.\n\n"
            "Steps:\n"
            "  1. Update .agent-flow/state/flow-context.yaml (task status → in_progress)\n"
            "  2. Create task packet: .agent-flow/artifacts/task-{id}-packet.md\n"
            "  3. Dispatch sub-agent:\n"
            '     Agent({description: "executor-{n}: {task}",\n'
            '            prompt: "Task: {description}\\nPacket: {path}",\n'
            '            subagent_type: "general-purpose"})\n'
            "  4. After completion: read only L2 summary → update flow-context.yaml\n"
            "  5. For Medium/Complex: dispatch Verifier agent for spot-check\n"
            "</system-reminder>"
        )
    elif complexity in ("medium", "complex"):
        strength = "MUST" if complexity == "complex" else "should consider"

        team_info = ""
        if team_mode == "full-team":
            team_info = (
                "\n\n"
                "Agent Team is ACTIVE (full-team mode):\n"
                "  - Searcher: dispatched during THINK for knowledge retrieval\n"
                "  - Executor: MUST be dispatched for code implementation\n"
                "  - Verifier: MUST be dispatched for independent acceptance\n"
                "  - Main Agent: coordinator ONLY — prohibited from direct search/implementation/verification\n"
                "  - Reference: .dev-workflow/skills/agent-team-init/handler.md"
            )
        elif team_mode == "search-only":
            team_info = (
                "\n\n"
                "Agent Team is ACTIVE (search-only mode):\n"
                "  - Searcher: dispatched during THINK for knowledge retrieval\n"
                "  - Main Agent: should still delegate code implementation to sub-agents for context isolation"
            )

        print(
            "<system-reminder>\n"
            f"[AgentFlow DISPATCH] {complexity.upper()} task in EXECUTE phase — "
            f"sub-agent delegation {strength}.\n\n"
            f"Task complexity: {complexity.upper()}\n"
            f"Context budget: {budget_status}\n\n"
            "Complex tasks benefit from sub-agent delegation to:\n"
            "  - Preserve main agent context for state management\n"
            "  - Enable parallel execution of independent subtasks\n"
            "  - Ensure quality through Verifier agent spot-checks\n\n"
            "Reference: ~/.agent-flow/skills/agent-orchestration/main-agent-dispatch/handler.md"
            f"{team_info}\n"
            "</system-reminder>"
        )


if __name__ == "__main__":
    main()
