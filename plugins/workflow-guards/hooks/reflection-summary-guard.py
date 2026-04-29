#!/usr/bin/env python3
"""Prompt reflection summary after task completion based on complexity.

UserPromptSubmit hook:
- If task is past IMPLEMENT and complexity is medium/complex
- Require reflection marker `.task-reflection-done`
- Auto-create reflection draft in wiki or skills based on task type
"""

from __future__ import annotations

import datetime as _dt
import re
import sys
from pathlib import Path

from contract_utils import get_complexity_level, read_state_path, structured_marker_exists


def _find_project_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _read_current_phase(project_root: Path) -> str:
    phase_path = read_state_path(project_root, "current_phase.md")
    if phase_path.is_file():
        try:
            return phase_path.read_text(encoding="utf-8")
        except OSError:
            return ""
    return ""


def _is_past_implement_phase(phase_content: str) -> bool:
    text = phase_content.lower()
    if "- implement:" in text and "completed" in text:
        return True
    return "verify" in text or "reflect" in text or "验收" in phase_content


def _extract_task_label(phase_content: str) -> str:
    for line in phase_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# 任务:"):
            return stripped.split(":", 1)[1].strip()
        if stripped.startswith("# Task:"):
            return stripped.split(":", 1)[1].strip()
    return "current-task"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip().lower()).strip("-")
    return slug or "task"


def _read_task_type(project_root: Path) -> str:
    task_list = read_state_path(project_root, "task-list.md")
    if not task_list.is_file():
        return "feature"
    try:
        content = task_list.read_text(encoding="utf-8")
    except OSError:
        return "feature"
    for line in content.splitlines():
        row = line.strip()
        if not row.startswith("|"):
            continue
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[1] in {"任务类型", "---", "待补充"}:
            continue
        if cells[1]:
            return cells[1].lower()
    return "feature"


def _target_kind(task_type: str) -> str:
    reusable_keywords = ("pattern", "workflow", "tool", "automation", "template", "reusable", "skill")
    if any(k in task_type for k in reusable_keywords):
        return "skill"
    return "wiki"


def _ensure_reflection_draft(project_root: Path, task_label: str, task_type: str) -> Path:
    today = _dt.date.today().isoformat()
    slug = _slugify(task_label)
    kind = _target_kind(task_type)
    if kind == "skill":
        path = project_root / ".agent-flow" / "skills" / "retrospectives" / f"{today}-{slug}" / "SKILL.md"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "---\n"
                f"name: retrospective-{slug}\n"
                "trigger: retrospective\n"
                "confidence: 0.6\n"
                "---\n\n"
                f"# Retrospective Skill ({task_label})\n\n"
                "## 遇到的问题\n"
                "- \n\n"
                "## 解决方案\n"
                "- \n\n"
                "## 可复用规则\n"
                "- \n",
                encoding="utf-8",
            )
        return path

    path = project_root / ".agent-flow" / "wiki" / "retrospectives" / f"{today}-{slug}.md"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            f"title: retrospective-{slug}\n"
            f"task_type: {task_type}\n"
            "---\n\n"
            f"# 任务复盘: {task_label}\n\n"
            "## 遇到的问题\n"
            "- \n\n"
            "## 如何解决\n"
            "- \n\n"
            "## 需要改进\n"
            "- \n",
            encoding="utf-8",
        )
    return path


def main() -> None:
    try:
        _ = sys.stdin.read()
    except Exception:
        pass

    project_root = _find_project_root()
    if project_root is None:
        return

    complexity = get_complexity_level(project_root)
    if complexity == "simple":
        return

    phase_content = _read_current_phase(project_root)
    if not phase_content or not _is_past_implement_phase(phase_content):
        return

    marker = read_state_path(project_root, ".task-reflection-done")
    if structured_marker_exists(marker, ("timestamp", "task", "confirmed_by", "summary")):
        return

    task_label = _extract_task_label(phase_content)
    task_type = _read_task_type(project_root)
    draft_path = _ensure_reflection_draft(project_root, task_label, task_type)
    target_kind = _target_kind(task_type)

    level_word = "MUST" if complexity == "complex" else "SHOULD"
    print(
        "<system-reminder>\n"
        f"[AgentFlow REFLECTION] {complexity.upper()} task completed — reflection {level_word} be done.\n\n"
        f"Task: {task_label}\n"
        f"Task type: {task_type}\n"
        f"Suggested sink: {target_kind}\n"
        f"Draft created: {draft_path}\n\n"
        "Please summarize:\n"
        "  1. 遇到了哪些问题\n"
        "  2. 如何解决\n"
        "  3. 还需要改进什么\n\n"
        "After user confirms reflection, write marker:\n"
        "  .agent-flow/state/.task-reflection-done\n"
        "  fields: phase=reflect, status=done, timestamp=..., task=..., confirmed_by=user, summary=...\n"
        "</system-reminder>"
    )


if __name__ == "__main__":
    main()

