#!/usr/bin/env python3
"""Hard-block execution when hook/tool readiness is not satisfied."""

from __future__ import annotations

import json
import sys

from contract_utils import (
    NO_RETRY_LINE,
    UNBLOCK_SUFFIX,
    agent_flow_hook_registration_status,
    find_project_root,
    has_agent_flow_hooks,
    is_cli_available,
    is_code_file,
    is_readonly_bash,
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


def _block_for_broken_hook_paths(target: str, missing_paths: list[str]) -> None:
    shown = "\n".join(f"  - {p}" for p in missing_paths[:5])
    print(
        "[AgentFlow BLOCKED] 检测到 agent-flow hooks 已注册，但脚本文件不存在，禁止继续执行可变更操作。\n"
        f"{NO_RETRY_LINE}\n\n"
        "✅ 解除方法：\n"
        "  1. 重新执行 `agent-flow init`（确保 .agent-flow 初始化完整）\n"
        "  2. 重新安装/启用所需插件（例如 workflow-guards）\n"
        "  3. 执行 `agent-flow plugin verify` 确认 missing/stale hooks 为 0\n"
        f"  4. 缺失脚本:\n{shown}\n"
        f"  5. 目标: {target}\n"
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

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if command.startswith("lark-cli") and not is_cli_available("lark-cli"):
            _block_for_missing_cli("lark-cli", command)
            sys.exit(2)
        if command.startswith("jira") and not is_cli_available("jira"):
            _block_for_missing_cli("jira", command)
            sys.exit(2)

    has_hooks = has_agent_flow_hooks(project_root)
    hooks_ok, missing_paths = agent_flow_hook_registration_status(project_root)
    if has_hooks and hooks_ok:
        sys.exit(0)

    if tool_name in {"Write", "Edit", "MultiEdit"}:
        file_path = str(tool_input.get("file_path", ""))
        if is_code_file(file_path):
            if has_hooks and missing_paths:
                _block_for_broken_hook_paths(file_path, missing_paths)
                sys.exit(2)
            _block_for_missing_hooks(file_path)
            sys.exit(2)
        sys.exit(0)

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if is_readonly_bash(command):
            sys.exit(0)
        if has_hooks and missing_paths:
            _block_for_broken_hook_paths(command[:120], missing_paths)
            sys.exit(2)
        _block_for_missing_hooks(command[:120])
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
