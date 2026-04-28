#!/usr/bin/env python3
"""Track clarification questions and requirement-context readiness markers.

PostToolUse hook:
- AskUserQuestion -> set `.clarification-recheck-required` as pending
- Any non-readonly execution / code edit -> resolve pending marker
- Requirement analysis stage -> set `.backend-context-required` as pending
- Backend doc evidence or data-format confirmation -> set `.backend-context-ready`
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import (
    find_project_root,
    is_readonly_bash,
    read_state_path,
    write_state_path,
)

REQUIRED_MARKER = ".clarification-recheck-required"
PENDING_MARKER = ".manual-stop-pending"
BACKEND_REQUIRED_MARKER = ".backend-context-required"
BACKEND_READY_MARKER = ".backend-context-ready"

REQUIREMENT_HINTS = (
    "feishu.cn/wiki",
    "需求文档",
    "requirement",
    "prd",
    "requirement-decomposition",
    "frontend-requirement-list-template",
    "前端需求",
)

BACKEND_DOC_HINTS = (
    "后端",
    "backend",
    "api",
    "openapi",
    "swagger",
    "接口文档",
    "数据模型",
    "鉴权",
    "错误码",
)

DATA_FORMAT_HINTS = (
    "数据格式",
    "字段",
    "输入输出",
    "schema",
    "接口约束",
    "返回结构",
)


def _resolve_pending(project_root) -> None:
    for marker_name in (REQUIRED_MARKER, PENDING_MARKER):
        pending = read_state_path(project_root, marker_name)
        if not pending.is_file():
            continue
        pending.write_text(
            f"timestamp={int(time.time())}\nstatus=resolved\nreason=progress-after-clarification\n",
            encoding="utf-8",
        )


def _extract_target(tool_name: str, tool_input: dict) -> str:
    if tool_name in {"Read", "Glob"}:
        return str(tool_input.get("file_path", "") or tool_input.get("path", ""))
    if tool_name == "Grep":
        return f"{tool_input.get('path','')} {tool_input.get('pattern','')}"
    if tool_name == "Bash":
        return str(tool_input.get("command", ""))
    if tool_name == "Skill":
        return str(tool_input)
    if tool_name == "AskUserQuestion":
        return str(tool_input.get("question", ""))
    return ""


def _set_backend_required(project_root, source: str) -> None:
    required_path = write_state_path(project_root, BACKEND_REQUIRED_MARKER)
    ready_path = read_state_path(project_root, BACKEND_READY_MARKER)
    if ready_path.is_file():
        return
    required_path.parent.mkdir(parents=True, exist_ok=True)
    required_path.write_text(
        f"timestamp={int(time.time())}\nstatus=pending\nreason=backend-context-check-required\nsource={source[:200]}\n",
        encoding="utf-8",
    )


def _set_backend_ready(project_root, source: str, mode: str) -> None:
    ready_path = write_state_path(project_root, BACKEND_READY_MARKER)
    ready_path.parent.mkdir(parents=True, exist_ok=True)
    ready_path.write_text(
        f"timestamp={int(time.time())}\nstatus=ready\nmode={mode}\nsource={source[:200]}\n",
        encoding="utf-8",
    )
    required_path = read_state_path(project_root, BACKEND_REQUIRED_MARKER)
    if required_path.is_file():
        required_path.write_text(
            f"timestamp={int(time.time())}\nstatus=resolved\nreason=backend-context-ready\n",
            encoding="utf-8",
        )


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        return

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    target = _extract_target(tool_name, tool_input).lower()

    if tool_name in {"Read", "Grep", "Glob", "Bash", "Skill"} and any(h in target for h in REQUIREMENT_HINTS):
        _set_backend_required(project_root, target)

    if any(h in target for h in BACKEND_DOC_HINTS) and tool_name in {"Read", "Grep", "Glob", "Bash", "Skill"}:
        _set_backend_ready(project_root, target, mode="backend-doc")

    if tool_name == "AskUserQuestion" and any(h in target for h in DATA_FORMAT_HINTS):
        _set_backend_ready(project_root, target, mode="user-confirmation")

    if tool_name == "AskUserQuestion":
        # Set clarification-recheck-required
        marker = write_state_path(project_root, REQUIRED_MARKER)
        marker.parent.mkdir(parents=True, exist_ok=True)
        question = ""
        if isinstance(tool_input, dict):
            question = str(tool_input.get("question", "")).strip().replace("\n", " ")[:200]
        marker.write_text(
            f"timestamp={int(time.time())}\n"
            "status=pending\n"
            f"question={question or 'unspecified'}\n"
            "reason=post-clarification-recheck-required\n",
            encoding="utf-8",
        )

        # Set manual-stop-pending
        stop_marker = write_state_path(project_root, PENDING_MARKER)
        stop_marker.parent.mkdir(parents=True, exist_ok=True)
        stop_marker.write_text(
            f"timestamp={int(time.time())}\nstatus=pending\nreason=waiting-for-next-gate-or-progress\n",
            encoding="utf-8",
        )
        return

    # Any substantive progress resolves both markers
    if tool_name in {"Write", "Edit", "MultiEdit"}:
        _resolve_pending(project_root)
        return

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if not is_readonly_bash(command):
            _resolve_pending(project_root)


if __name__ == "__main__":
    main()
