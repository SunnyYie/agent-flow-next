#!/usr/bin/env python3
"""
AgentFlow Parallel Execution Enforcer — UserPromptSubmit hook.
Remind about parallel execution when multiple independent subtasks exist.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def _find_project_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists():
            return parent
        if parent == Path.home():
            break
    return None


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


def _extract_subtasks(phase_content: str) -> list[dict]:
    subtasks: list[dict] = []
    in_plan = False

    for line in phase_content.splitlines():
        stripped = line.strip()
        if "实施计划" in stripped or "Implementation Plan" in stripped:
            in_plan = True
            continue
        if in_plan and stripped.startswith("## ") and "实施计划" not in stripped:
            in_plan = False
            continue
        if not in_plan:
            continue

        match = re.match(r"^-\s+(T\d+):\s+(.+)$", stripped)
        if not match:
            continue

        task_id = match.group(1)
        description = match.group(2)
        status = "pending"
        if "✅" in description or "completed" in description.lower():
            status = "completed"
        elif "🔄" in description or "in_progress" in description.lower():
            status = "in_progress"

        dependencies: list[str] = []
        dep_match = re.search(r"[（(]([^）)]+)[）)]", description)
        if dep_match:
            dependencies = re.findall(r"T\d+", dep_match.group(1))

        subtasks.append(
            {
                "id": task_id,
                "description": description,
                "status": status,
                "dependencies": dependencies,
            }
        )
    return subtasks


def _parse_dependency_line(phase_content: str) -> str | None:
    for line in phase_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("依赖:") or stripped.startswith("依赖："):
            return stripped.split(":", 1)[1].strip() if ":" in stripped else stripped.split("：", 1)[1].strip()
    return None


def _find_parallelizable_groups(subtasks: list[dict], dep_line: str | None) -> list[list[str]]:
    pending = [task for task in subtasks if task["status"] != "completed"]
    if len(pending) < 2:
        return []

    if dep_line:
        if "→" in dep_line and "[" not in dep_line:
            return []
        groups: list[list[str]] = []
        for bracket in re.findall(r"\[([^\]]+)\]", dep_line):
            task_ids = re.findall(r"T\d+", bracket)
            if len(task_ids) < 2:
                continue
            pending_ids = [task["id"] for task in pending]
            parallel_ids = [tid for tid in task_ids if tid in pending_ids]
            if len(parallel_ids) >= 2:
                groups.append(parallel_ids)
        return groups

    pending_ids = {task["id"] for task in pending}
    no_dep_tasks = [
        task for task in pending if not task["dependencies"] or not any(dep in pending_ids for dep in task["dependencies"])
    ]
    if len(no_dep_tasks) >= 2:
        return [[task["id"] for task in no_dep_tasks]]
    return []


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
        return

    subtasks = _extract_subtasks(phase_content)
    if len(subtasks) < 2:
        return

    parallel_groups = _find_parallelizable_groups(subtasks, _parse_dependency_line(phase_content))
    if not parallel_groups:
        return

    groups_text = "; ".join(", ".join(group) for group in parallel_groups)
    pending_count = sum(1 for task in subtasks if task["status"] == "pending")
    completed_count = sum(1 for task in subtasks if task["status"] == "completed")

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
