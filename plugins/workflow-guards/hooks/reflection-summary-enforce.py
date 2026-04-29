#!/usr/bin/env python3
"""Enforce reflection summary before push/MR for medium/complex tasks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from contract_utils import NO_RETRY_LINE, UNBLOCK_SUFFIX, find_project_root as _shared_find_project_root, get_complexity_level, read_state_path, structured_marker_exists


def _find_project_root() -> Path | None:
    return _shared_find_project_root()


def _read_current_phase(project_root: Path) -> str:
    phase = read_state_path(project_root, "current_phase.md")
    if phase.is_file():
        try:
            return phase.read_text(encoding="utf-8")
        except OSError:
            return ""
    return ""


def _is_past_implement_phase(phase_content: str) -> bool:
    text = phase_content.lower()
    if "- implement:" in text and "completed" in text:
        return True
    return "verify" in text or "reflect" in text or "验收" in phase_content


def _is_push_or_mr(command: str) -> bool:
    cmd = command.strip().lower()
    return cmd.startswith("git push") or cmd.startswith("glab mr")


def main() -> None:
    project_root = _find_project_root()
    if project_root is None:
        sys.exit(0)

    complexity = get_complexity_level(project_root)
    if complexity == "simple":
        sys.exit(0)

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    if payload.get("tool_name", "") != "Bash":
        sys.exit(0)
    command = str(payload.get("tool_input", {}).get("command", ""))
    if not _is_push_or_mr(command):
        sys.exit(0)

    phase_content = _read_current_phase(project_root)
    if not phase_content or not _is_past_implement_phase(phase_content):
        sys.exit(0)

    marker = read_state_path(project_root, ".task-reflection-done")
    if structured_marker_exists(marker, ("timestamp", "task", "confirmed_by", "summary")):
        sys.exit(0)

    print(
        "[AgentFlow BLOCKED] 推送/MR 前必须完成任务反思总结（中高复杂度任务）。\n"
        f"{NO_RETRY_LINE}\n\n"
        "✅ 解除方法：\n"
        "  1. 补全 .agent-flow/wiki/retrospectives 或 .agent-flow/skills/retrospectives 的反思草稿\n"
        "  2. 与用户确认问题、解决方案、改进项\n"
        "  3. 写入 .agent-flow/state/.task-reflection-done\n"
        "     phase=reflect\n"
        "     status=done\n"
        "     timestamp=ISO8601\n"
        "     task=current-task\n"
        "     confirmed_by=user\n"
        "     summary=反思摘要\n"
        f"  {UNBLOCK_SUFFIX}\n"
        f"目标命令: {command[:120]}"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
