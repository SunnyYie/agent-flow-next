#!/usr/bin/env python3
"""
AgentFlow Parallel Execution Enforcer — UserPromptSubmit hook

Remind about parallel execution when multiple independent subtasks exist.

Logic:
  - Read current_phase.md
  - If there are multiple pending subtasks with no dependencies between them,
    print reminder to execute in parallel

Output: <system-reminder> block with parallel execution reminder.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


def _find_project_root() -> Path | None:
    cwd = Path.cwd().resolve()
    candidates = [candidate for candidate in [cwd, *cwd.parents] if (candidate / ".agent-flow").exists()]
    if not candidates:
        return None
    git_root: Path | None = None
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            git_root = Path(proc.stdout.strip()).resolve()
    except OSError:
        git_root = None
    if git_root is None:
        for candidate in [cwd, *cwd.parents]:
            if (candidate / ".git").exists():
                git_root = candidate
                break
    if git_root is not None:
        if (git_root / ".agent-flow").exists():
            return git_root
        in_repo = [c for c in candidates if git_root == c or git_root in c.parents]
        if in_repo:
            return in_repo[-1]
    return candidates[0]


def _read_current_phase(project_root: Path) -> str:
    """Read current_phase.md content."""
    phase_path = project_root / ".agent-flow/state" / "current_phase.md"
    if phase_path.is_file():
        try:
            return phase_path.read_text(encoding="utf-8")
        except OSError:
            pass
    return ""


def _get_complexity_level(project_root: Path) -> str:
    """Read complexity level from .complexity-level file."""
    path = project_root / ".agent-flow/state" / ".complexity-level"
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


def _extract_subtasks(phase_content: str) -> list[dict]:
    """Extract subtasks from current_phase.md implementation plan.

    Returns list of dicts with keys: id, description, status, dependencies.
    """
    subtasks = []
    in_plan = False

    for line in phase_content.splitlines():
        stripped = line.strip()

        # Detect implementation plan section
        if "实施计划" in stripped or "Implementation Plan" in stripped:
            in_plan = True
            continue

        # Leave implementation plan section
        if in_plan and stripped.startswith("## ") and "实施计划" not in stripped:
            in_plan = False
            continue

        if not in_plan:
            continue

        # Match subtask lines like "- T1: Description" or "- T1: Description（dependency info）"
        match = re.match(r"^-\s+(T\d+):\s+(.+)$", stripped)
        if match:
            task_id = match.group(1)
            description = match.group(2)

            # Check for status markers
            status = "pending"
            if "✅" in description or "completed" in description.lower():
                status = "completed"
            elif "🔄" in description or "in_progress" in description.lower():
                status = "in_progress"

            # Check for dependency info in parentheses
            dependencies = []
            dep_match = re.search(r"[（(]([^）)]+)[）)]", description)
            if dep_match:
                dep_text = dep_match.group(1)
                # Look for dependency patterns like "T1→T2" or "depends on T1"
                dep_ids = re.findall(r"T\d+", dep_text)
                dependencies = dep_ids

            subtasks.append({
                "id": task_id,
                "description": description,
                "status": status,
                "dependencies": dependencies,
            })

    return subtasks


def _parse_dependency_line(phase_content: str) -> str | None:
    """Parse the dependency line from current_phase.md (e.g., '依赖: T1→T2→T3')."""
    for line in phase_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("依赖:") or stripped.startswith("依赖："):
            return stripped.split(":", 1)[1].strip() if ":" in stripped else stripped.split("：", 1)[1].strip()
    return None


def _find_parallelizable_groups(subtasks: list[dict], dep_line: str | None) -> list[list[str]]:
    """Find groups of subtasks that can be executed in parallel.

    Returns a list of groups, where each group is a list of task IDs
    that have no dependencies on each other.
    """
    pending = [t for t in subtasks if t["status"] != "completed"]
    if len(pending) < 2:
        return []

    # Parse dependency graph from dep_line (e.g., "T1→T2→T3" or "T1→[T2,T3]→T4")
    if dep_line:
        # Sequential pattern: T1→T2→T3 — no parallelism
        if "→" in dep_line and "[" not in dep_line:
            # Pure sequential — check if there are at least 2 consecutive pending tasks
            # that could potentially be parallelized
            return []

        # Parallel pattern: T1→[T2,T3]→T4 — T2 and T3 are parallelizable
        groups = []
        import re as re2
        bracket_groups = re2.findall(r"\[([^\]]+)\]", dep_line)
        for bg in bracket_groups:
            task_ids = re2.findall(r"T\d+", bg)
            if len(task_ids) >= 2:
                # Filter to only pending tasks
                pending_ids = [t["id"] for t in pending]
                parallel_ids = [tid for tid in task_ids if tid in pending_ids]
                if len(parallel_ids) >= 2:
                    groups.append(parallel_ids)
        return groups

    # No dependency line — check individual task dependencies
    # Tasks with no dependencies on each other can be parallelized
    pending_ids = {t["id"] for t in pending}
    no_dep_tasks = [t for t in pending if not t["dependencies"] or not any(d in pending_ids for d in t["dependencies"])]
    if len(no_dep_tasks) >= 2:
        return [[t["id"] for t in no_dep_tasks]]

    return []


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

    # Simple tasks don't need parallel enforcement
    complexity = _get_complexity_level(project_root)
    if complexity == "simple":
        return

    # Extract subtasks
    subtasks = _extract_subtasks(phase_content)
    if len(subtasks) < 2:
        return

    # Parse dependency line
    dep_line = _parse_dependency_line(phase_content)

    # Find parallelizable groups
    parallel_groups = _find_parallelizable_groups(subtasks, dep_line)
    if not parallel_groups:
        return

    # Build reminder message
    group_descriptions = []
    for group in parallel_groups:
        group_descriptions.append(", ".join(group))

    groups_text = "; ".join(group_descriptions)

    # Count pending tasks
    pending_count = sum(1 for t in subtasks if t["status"] == "pending")
    completed_count = sum(1 for t in subtasks if t["status"] == "completed")

    print(
        "<system-reminder>\n"
        f"[AgentFlow PARALLEL] {pending_count} pending subtasks detected with "
        f"parallelizable groups: {groups_text}\n\n"
        "Independent subtasks should be executed in parallel to save time.\n\n"
        "How to execute in parallel:\n"
        "  - Send multiple Agent tool calls in a single message\n"
        "  - Each agent handles one independent subtask\n"
        "  - Example:\n"
        "    Agent({description: \"executor-1: Task1\", ...})\n"
        "    Agent({description: \"executor-2: Task2\", ...})\n\n"
        f"Task progress: {completed_count}/{len(subtasks)} completed, "
        f"{pending_count} pending\n"
        f"Complexity: {complexity.upper()}\n"
        "</system-reminder>"
    )


if __name__ == "__main__":
    main()
