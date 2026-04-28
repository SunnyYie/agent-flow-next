#!/usr/bin/env python3
"""Block implementation until post-question recheck is recorded and progress made.

PreToolUse hook:
- If `.clarification-recheck-required` is pending and `.clarification-recheck-done`
  is absent, code-changing actions and repeated AskUserQuestion are blocked.
- If `.manual-stop-pending` is pending (no progress since last question),
  repeated AskUserQuestion is blocked unless a phase-gate is ready.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import (
    find_project_root,
    is_code_file,
    is_readonly_bash,
    load_marker_entries,
    NO_RETRY_LINE,
    read_state_path,
    UNBLOCK_SUFFIX,
)

PENDING_MARKER = ".manual-stop-pending"
GATE_MARKER = ".phase-gate-ready"
BACKEND_REQUIRED_MARKER = ".backend-context-required"
BACKEND_READY_MARKER = ".backend-context-ready"


def _is_pending(path) -> bool:
    if not path.is_file():
        return False
    entries = load_marker_entries(path)
    if not entries:
        return path.stat().st_size > 0
    for entry in entries:
        status = str(entry.get("status", "")).strip().lower()
        if status in {"resolved", "done", "confirmed", "closed"}:
            continue
        return True
    return False


def _is_recheck_done(path) -> bool:
    if not path.is_file():
        return False
    for entry in load_marker_entries(path):
        status = str(entry.get("status", "")).strip().lower()
        decision = str(entry.get("ready_to_implement", "")).strip().lower()
        has_summary = bool(str(entry.get("summary", "")).strip())
        if status in {"done", "confirmed", "resolved"} and decision in {"yes", "no"} and has_summary:
            return True
    return False


def _gate_ready(path) -> bool:
    if not path.is_file():
        return False
    entries = load_marker_entries(path)
    if not entries:
        return False
    entry = entries[-1]
    status = str(entry.get("status", "")).strip().lower()
    gate = str(entry.get("gate", "")).strip().upper()
    return status == "ready" and gate in {"G1", "G2", "G3", "G4"}


def _block(target: str, reason: str) -> None:
    print(
        "[AgentFlow BLOCKED] 澄清后复判未完成，禁止继续执行。\n"
        f"{NO_RETRY_LINE}\n\n"
        f"阻断原因: {reason}\n"
        f"目标: {target}\n\n"
        "✅ 解除方法：\n"
        "  1. 基于已获得的信息做一次复判：是否可开始实现、是否仍有关键边界未明\n"
        "  2. 写入 `.agent-flow/state/.clarification-recheck-done`：\n"
        "     status=done\n"
        "     ready_to_implement=yes|no\n"
        "     summary=复判结论\n"
        "  3. 同步将 `.clarification-recheck-required` 标记改为 resolved（或清空）\n"
        f"  {UNBLOCK_SUFFIX}"
    )


def _block_no_progress(target: str) -> None:
    print(
        "[AgentFlow BLOCKED] 检测到连续人工停顿：上一次询问后尚无实质进展。\n"
        f"{NO_RETRY_LINE}\n\n"
        "✅ 解除方法：\n"
        "  1. 先继续自动推进当前阶段（检索/实现/验证任一实质动作）\n"
        "  2. 如确需门控确认，先写入 .phase-gate-ready（status=ready, gate=G1..G4）\n"
        f"  {UNBLOCK_SUFFIX}"
    )


def _backend_ready(path) -> bool:
    if not path.is_file():
        return False
    for entry in load_marker_entries(path):
        if str(entry.get("status", "")).strip().lower() == "ready":
            mode = str(entry.get("mode", "")).strip().lower()
            if mode in {"backend-doc", "user-confirmation"}:
                return True
    return False


def _block_backend_context(target: str) -> None:
    print(
        "[AgentFlow BLOCKED] 需求拆解阶段缺少后端上下文确认，禁止继续执行可变更操作。\n"
        f"{NO_RETRY_LINE}\n\n"
        "阻断原因: 已进入需求文档拆解，但尚未满足“后端文档或数据格式确认”前置条件\n"
        f"目标: {target}\n\n"
        "✅ 解除方法（二选一）：\n"
        "  1. 提供并读取后端技术文档（接口/数据模型/鉴权/错误码等），写入 `.backend-context-ready`\n"
        "     status=ready\n"
        "     mode=backend-doc\n"
        "     source=后端文档链接或检索证据\n"
        "  2. 若无后端文档，先向用户确认关键数据格式/接口约束，再写入 `.backend-context-ready`\n"
        "     status=ready\n"
        "     mode=user-confirmation\n"
        "     source=用户确认摘要\n"
        f"  {UNBLOCK_SUFFIX}"
    )


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    # Check clarification recheck
    required_marker = read_state_path(project_root, ".clarification-recheck-required")
    done_marker = read_state_path(project_root, ".clarification-recheck-done")
    recheck_needed = _is_pending(required_marker) and not _is_recheck_done(done_marker)

    # Check automation progress
    pending_path = read_state_path(project_root, PENDING_MARKER)
    no_progress = _is_pending(pending_path)
    gate_path = read_state_path(project_root, GATE_MARKER)
    gate_allowed = _gate_ready(gate_path)
    backend_required = _is_pending(read_state_path(project_root, BACKEND_REQUIRED_MARKER))
    backend_ready = _backend_ready(read_state_path(project_root, BACKEND_READY_MARKER))
    backend_block = backend_required and not backend_ready

    if not recheck_needed and not no_progress and not backend_block:
        sys.exit(0)

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name == "AskUserQuestion":
        if no_progress and not gate_allowed:
            _block_no_progress("AskUserQuestion")
            sys.exit(2)
        if recheck_needed:
            _block("AskUserQuestion", "上一次提问后尚未完成复判")
            sys.exit(2)
        sys.exit(0)

    if tool_name in {"Write", "Edit", "MultiEdit"}:
        file_path = str(tool_input.get("file_path", ""))
        if backend_block and is_code_file(file_path):
            _block_backend_context(file_path)
            sys.exit(2)
        if recheck_needed and is_code_file(file_path):
            _block(file_path, "澄清复判未完成就尝试修改代码")
            sys.exit(2)
        sys.exit(0)

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if is_readonly_bash(command):
            sys.exit(0)
        if backend_block:
            _block_backend_context(command[:120])
            sys.exit(2)
        if recheck_needed:
            _block(command[:120], "澄清复判未完成就尝试执行变更命令")
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
