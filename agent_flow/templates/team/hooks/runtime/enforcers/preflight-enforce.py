#!/usr/bin/env python3
"""
AgentFlow Pre-Flight Enforcer — PreToolUse hook
在 pre-flight 未完成时，阻断执行类工具（Write/Edit/Bash执行命令），
只放行读取/搜索类工具（Read/Glob/Grep 等）和写入 agent-flow 文档的操作。

v2.0 新增：Simple 任务（快速路径）简化 pre-flight 要求，
只需 2 步搜索（全局 Skills + Wiki）+ complexity-level 标记即可放行。
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import (
    NO_RETRY_LINE,
    UNBLOCK_SUFFIX,
    find_project_root,
    get_complexity_level,
    read_state_path,
)


# 始终放行的工具（读取/搜索/交互类）
ALLOWED_TOOLS = {
    "Read", "Glob", "Grep", "Agent", "AskUserQuestion", "TodoWrite",
    "CronList", "CronDelete", "Skill", "WebSearch",
    "EnterPlanMode", "ExitPlanMode", "ScheduleWakeup",
    "mcp__supabase__authenticate", "mcp__supabase__complete_authentication",
}

# Bash 中允许的只读前缀（pre-flight 期间可用）
READONLY_BASH_PREFIXES = (
    "ls", "cat", "head", "tail", "find", "grep", "rg", "wc",
    "which", "pwd", "whoami", "uname", "env", "printenv", "echo",
    "type ", "command ", "git status", "git log", "git diff",
    "git branch", "git remote", "git rev-parse", "git show",
    "git stash", "git worktree", "lark-cli", "agent-flow",
    "python3 -c", "node -e",  # 用于 JSON 解析等轻量脚本
)

# Simple 任务简化 pre-flight 的标记文件
SIMPLE_PREFLIGHT_MARKER = ".agent-flow/state/.simple-preflight-done"


def is_agent_flow_path(file_path: str) -> bool:
    """判断文件路径是否属于 agent-flow 文档目录（pre-flight 期间允许写入）"""
    normalized = os.path.normpath(file_path)
    return (
        ".agent-flow/" in normalized
        or ".claude/" in normalized
    )


def is_readonly_bash(command: str) -> bool:
    """判断 Bash 命令是否为只读命令"""
    cmd = command.strip()
    for prefix in READONLY_BASH_PREFIXES:
        if cmd.startswith(prefix):
            return True
    return False


def is_safe_state_sync_bash(command: str) -> bool:
    """Allow syncing AgentFlow state files across repos during pre-flight."""
    cmd = " ".join(command.strip().split())
    if not cmd:
        return False
    m = re.match(r"^(cp|mv)\s+(\S+)\s+(\S+)$", cmd)
    if not m:
        return False
    src = m.group(2)
    dst = m.group(3)
    allowed_names = {
        "current_phase.md",
        ".complexity-level",
        ".simple-preflight-done",
    }
    src_name = os.path.basename(src)
    dst_name = os.path.basename(dst)
    if src_name != dst_name or src_name not in allowed_names:
        return False
    return ".agent-flow/state/" in src and ".agent-flow/state/" in dst


def _emit_block(message: str, action: str) -> None:
    text = (
        f"[AgentFlow BLOCKED] {message}\n"
        f"{NO_RETRY_LINE}\n\n"
        f"✅ 当前可执行操作：\n"
        f"{action}\n"
        f"{UNBLOCK_SUFFIX}"
    )
    print(text, file=sys.stderr)


def is_code_file_for_preflight(file_path: str) -> bool:
    """判断文件是否为代码文件（pre-flight 期间需要阻断的文件类型）"""
    _, ext = os.path.splitext(file_path)
    code_extensions = {
        ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".kt",
        ".swift", ".m", ".h", ".c", ".cpp", ".rb", ".php", ".vue", ".svelte",
        ".css", ".scss", ".less", ".html", ".sql", ".graphql",
        ".sh", ".bash", ".zsh",
    }
    code_filenames = {
        "package.json", "tsconfig.json", "Makefile", "Dockerfile",
        "Podfile", "Gemfile", "build.gradle", "settings.gradle",
    }
    if ext.lower() in code_extensions:
        return True
    if os.path.basename(file_path) in code_filenames:
        return True
    return False


def main():
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    # 检查 pre-flight 是否已完成
    phase_file = read_state_path(project_root, "current_phase.md")
    complexity_file = read_state_path(project_root, ".complexity-level")

    phase_found = os.path.isfile(phase_file) and os.path.getsize(phase_file) > 10

    if phase_found:
        # current_phase.md 存在，但还需要检查 .complexity-level 是否存在
        if os.path.isfile(complexity_file):
            sys.exit(0)  # Pre-flight 完成且复杂度已评估，放行所有工具
        else:
            # 有 current_phase.md 但没有 .complexity-level → 复杂度评估缺失
            # 只允许读取操作和 agent-flow 文档写入（完成评估用）
            pass

    # Simple 任务简化检查：如果有 .simple-preflight-done 标记，放行
    complexity = get_complexity_level(project_root)
    if complexity == "simple" and os.path.isfile(SIMPLE_PREFLIGHT_MARKER):
        sys.exit(0)  # Simple 任务简化 pre-flight 已完成，放行

    # 读取 hook 输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)  # 解析失败，放行（避免误阻）

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 1. 始终放行的工具
    if tool_name in ALLOWED_TOOLS:
        sys.exit(0)

    # 2. Write/Edit: 只允许写入 agent-flow 文档
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if is_agent_flow_path(file_path):
            sys.exit(0)  # 允许写入 agent-flow 文档

        # 非代码文件（如 README.md）在复杂度评估缺失时也允许
        if not is_code_file_for_preflight(file_path):
            sys.exit(0)

        # 代码文件：判断阻断原因
        if not os.path.isfile(phase_file) or os.path.getsize(phase_file) <= 10:
            _emit_block(
                f"Pre-flight 未完成，禁止修改代码文件: {file_path}\n"
                "缺少文件: .agent-flow/state/current_phase.md",
                "  1. 执行 pre-flight-check\n"
                "  2. 生成 .agent-flow/state/current_phase.md 后重试",
            )
        else:
            _emit_block(
                f"任务复杂度未评估，禁止修改代码文件: {file_path}\n"
                f"缺少文件: .agent-flow/state/.complexity-level",
                "  1. 执行 pre-flight-check Step 2\n"
                "  2. 生成 .agent-flow/state/.complexity-level 后重试",
            )
        sys.exit(2)

    # 3. Bash: 只允许只读命令
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if is_readonly_bash(command):
            sys.exit(0)  # 允许只读命令
        if is_safe_state_sync_bash(command):
            sys.exit(0)  # 允许同步状态文件
        # 允许 mkdir 创建 agent-flow 目录
        if command.strip().startswith("mkdir") and ".agent-flow" in command:
            sys.exit(0)

        if not os.path.isfile(phase_file) or os.path.getsize(phase_file) <= 10:
            _emit_block(
                f"Pre-flight 未完成，禁止执行命令: {command[:120]}\n"
                "当前阶段仅允许：只读命令、.agent-flow 文档写入、状态文件同步(cp/mv)。",
                "  1. 执行 pre-flight-check\n"
                "  2. 生成 .agent-flow/state/current_phase.md 后重试",
            )
        else:
            _emit_block(
                f"任务复杂度未评估，禁止执行命令: {command[:120]}\n"
                "当前阶段仅允许：只读命令、.agent-flow 文档写入、状态文件同步(cp/mv)。",
                "  1. 执行 pre-flight-check Step 2\n"
                "  2. 生成 .agent-flow/state/.complexity-level 后重试",
            )
        sys.exit(2)

    # 4. NotebookEdit: 阻断
    if tool_name == "NotebookEdit":
        _emit_block(
            "Pre-flight 未完成，禁止编辑 Notebook。",
            "  完成 pre-flight-check 的 5 个步骤后重试",
        )
        sys.exit(2)

    # 5. 其他工具：放行（CronCreate 等）
    sys.exit(0)


if __name__ == "__main__":
    main()
