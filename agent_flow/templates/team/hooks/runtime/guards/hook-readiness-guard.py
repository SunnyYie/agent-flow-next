#!/usr/bin/env python3
"""Hard-block execution when hook/tool readiness is not satisfied.

PreToolUse guard:
1) Block code-changing actions when .claude/settings*.json does not register
   any agent-flow hooks.
2) Block lark-cli/jira commands when the binary is unavailable in current PATH.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import (
    find_project_root,
    has_agent_flow_hooks,
    is_cli_available,
    is_code_file,
    is_readonly_bash,
    NO_RETRY_LINE,
    UNBLOCK_SUFFIX,
)


def _block_for_missing_hooks(target: str) -> None:
    print(
        "[AgentFlow BLOCKED] 未检测到 agent-flow hooks 注册，禁止继续执行可变更操作。\n"
        f"{NO_RETRY_LINE}\n\n"
        "✅ 解除方法：\n"
        "  1. 在 .claude/settings*.json 注册 agent-flow hooks\n"
        "  2. 确认 hooks 中包含 agent-flow/agent_flow 相关命令\n"
        f"  3. 目标: {target}\n"
        f"  {UNBLOCK_SUFFIX}"
    )


def _block_for_missing_cli(cli_name: str, command: str) -> None:
    print(
        f"[AgentFlow BLOCKED] 命令依赖 `{cli_name}`，但当前 shell PATH 不可用。\n"
        f"{NO_RETRY_LINE}\n\n"
        "✅ 解除方法：\n"
        f"  1. 安装并验证 `{cli_name}`: which {cli_name}\n"
        "  2. 若交互终端可用但 hook 子进程不可用，请修复登录 shell PATH\n"
        f"  3. 目标命令: {command[:120]}\n"
        f"  {UNBLOCK_SUFFIX}"
    )


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    # lark-cli / jira 命令可执行性硬检查
    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if command.startswith("lark-cli") and not is_cli_available("lark-cli"):
            _block_for_missing_cli("lark-cli", command)
            sys.exit(2)
        if command.startswith("jira") and not is_cli_available("jira"):
            _block_for_missing_cli("jira", command)
            sys.exit(2)

    # hooks 就绪硬检查（仅拦截可变更操作）
    if has_agent_flow_hooks(project_root):
        sys.exit(0)

    if tool_name in {"Write", "Edit", "MultiEdit"}:
        file_path = str(tool_input.get("file_path", ""))
        if is_code_file(file_path):
            _block_for_missing_hooks(file_path)
            sys.exit(2)
        sys.exit(0)

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if is_readonly_bash(command):
            sys.exit(0)
        _block_for_missing_hooks(command[:120])
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
