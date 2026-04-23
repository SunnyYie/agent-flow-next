#!/usr/bin/env python3
"""
AgentFlow Error Search Reminder — PostToolUse hook.
当 Bash 命令失败时提醒先搜索；连续失败达到阈值时升级为人工决策提醒。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from contract_utils import find_project_root, read_state_path, write_state_path

MAX_ERROR_ROUNDS = 2

ERROR_INDICATORS = [
    "Error:",
    "error:",
    "ERROR:",
    "Failed",
    "failed",
    "FAILED",
    "exit code: 1",
    "exit code: 2",
    "exit code: 127",
    "404 Not Found",
    "404",
    "500",
    "403 Forbidden",
    "not found",
    "Not Found",
    "Permission denied",
    "permission denied",
    "Cannot find",
    "cannot find",
    "No such file",
    "no such file",
    "fatal:",
    "Fatal:",
    "exception",
    "Exception",
    "Traceback",
]


def _error_count_path(project_root: Path) -> Path:
    return write_state_path(project_root, ".error-count")


def read_error_count(project_root: Path) -> int:
    path = _error_count_path(project_root)
    try:
        if path.is_file():
            return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return 0


def write_error_count(project_root: Path, count: int) -> None:
    path = _error_count_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(str(count), encoding="utf-8")
    except OSError:
        pass


def reset_error_count(project_root: Path) -> None:
    for path in {
        write_state_path(project_root, ".error-count"),
        read_state_path(project_root, ".error-count"),
    }:
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    try:
        raw_input = sys.stdin.read()
        input_data = json.loads(raw_input) if raw_input else {}
    except Exception:
        sys.exit(0)

    if input_data.get("tool_name", "") != "Bash":
        sys.exit(0)

    tool_result = str(input_data.get("tool_result", ""))
    tool_input = input_data.get("tool_input", {}) or {}
    stderr = str(tool_input.get("stderr", ""))
    combined_output = f"{tool_result}\n{stderr}"
    has_error = any(indicator in combined_output for indicator in ERROR_INDICATORS)

    if not has_error:
        reset_error_count(project_root)
        sys.exit(0)

    count = read_error_count(project_root) + 1
    write_error_count(project_root, count)
    command = str(tool_input.get("command", "unknown"))

    if count >= MAX_ERROR_ROUNDS:
        print(
            f"[AgentFlow ESCALATE] 思维链已循环 {count} 次仍未解决，必须暂停！\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"命令: {command[:80]}\n"
            f"连续失败次数: {count}/{MAX_ERROR_ROUNDS}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⛔ 强制暂停执行，必须请求人工决策:\n"
            "  1. 向用户详细描述遇到的问题\n"
            "  2. 列出已尝试的方案和失败原因\n"
            "  3. 提出可能的解决方案供用户选择\n"
            "  4. 等待用户明确指示后才能继续\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ 禁止: 自行推测新方案、继续尝试、跳过此问题"
        )
    else:
        print(
            f"[AgentFlow ERROR WARNING] 命令执行失败 (第{count}/{MAX_ERROR_ROUNDS}轮): {command[:80]}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ 严厉禁止以下行为:\n"
            "  ❌ 自行推测原因并重试\n"
            "  ❌ 凭经验猜测解决方案\n"
            "  ❌ 忽略错误继续执行\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ 必须执行以下步骤:\n"
            "  1. Grep 搜索 ~/.agent-flow/skills/ 查找相关 Skill\n"
            "  2. Grep 搜索 ~/.agent-flow/wiki/pitfalls/ 查找已知坑\n"
            "  3. Grep 搜索 .agent-flow/skills/ 查找项目 Skill\n"
            "  4. 找到匹配 → 严格按 Skill/经验执行\n"
            "  5. 未找到 → 向用户描述问题并请求指导\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ 再失败 {MAX_ERROR_ROUNDS - count} 次将强制暂停，请求人工决策"
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
