#!/usr/bin/env python3
"""
AgentFlow Thinking Chain Enforcer — PreToolUse hook
强制思维链执行模式（硬性要求）：
  思考 → 搜索解决方案 → 确认方案 → 执行 → 验证 → 未解决则继续思考

核心机制：
  Agent 搜索了 Skills/Wiki → search-tracker.py 创建 .search-done 标记
  Agent 执行代码修改 → 本 hook 检查标记 → 无标记 = 没搜索 = 阻断

按复杂度分级调整行为（v3.0）：
  Simple:  跳过思维链检查（简单任务无需搜索先行）
  Medium:  搜索标记有效期 15 分钟，硬阻断
  Complex: 搜索标记有效期 10 分钟，硬阻断

仅对代码文件修改和执行命令生效，不影响读取/搜索操作。
"""
import json
import os
import sys
import time

from contract_utils import (
    NO_RETRY_LINE,
    UNBLOCK_SUFFIX,
    find_project_root,
    get_complexity_level,
    read_state_path,
)

# 各复杂度的搜索标记有效期（秒）
MAX_SEARCH_AGE_MAP = {
    "medium": 900,  # 15 分钟
    "complex": 600,  # 10 分钟
}
DEFAULT_MAX_SEARCH_AGE = 900  # 默认 Medium

# 代码文件扩展名
CODE_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".swift",
    ".m",
    ".h",
    ".c",
    ".cpp",
    ".rb",
    ".php",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".less",
    ".html",
    ".sql",
    ".graphql",
    ".sh",
    ".bash",
    ".zsh",
}

CODE_FILENAMES = {
    "package.json",
    "tsconfig.json",
    "Makefile",
    "Dockerfile",
    "Podfile",
    "Gemfile",
    "build.gradle",
    "settings.gradle",
    "app.json",
    "babel.config.js",
    "metro.config.js",
}

# 允许写入的路径（不受思维链检查限制）
ALLOWED_PATH_PREFIXES = (".agent-flow", ".dev-workflow", ".claude")

# 只读 Bash 命令前缀（不需要搜索标记）
READONLY_BASH_PREFIXES = (
    "ls",
    "cat",
    "head",
    "tail",
    "find",
    "grep",
    "rg",
    "wc",
    "which",
    "pwd",
    "whoami",
    "uname",
    "env",
    "printenv",
    "echo",
    "type ",
    "command ",
    "git status",
    "git log",
    "git diff",
    "git branch",
    "git remote",
    "git rev-parse",
    "git show",
    "git stash",
    "git worktree",
    "git checkout",
    "git switch",
    "git pull",
    "git fetch",
    "lark-cli",
    "agent-flow",
    "python3",
    "python",
    "node",
    ".venv/bin/python",
    # 测试命令（只读，不修改代码）
    "pytest",
    ".venv/bin/pytest",
    ".venv/bin/python -m pytest",
    "npx tsx",
    "npx",
    # 系统管理命令（非代码修改）
    "mkdir",
    "chmod",
    "touch",
    "cp",
    "mv",
    "ln",
    "tar",
    "zip",
    "unzip",
    "xxd",
    "curl"
)

# 思维链提示信息
CHAIN_PROMPT = f"""[AgentFlow BLOCKED] 思维链未完成 — 你没有先搜索知识库就尝试执行！

{NO_RETRY_LINE}

✅ 解除方法：完成以下前置条件后，当前操作会自动放行：
  1. 思考   : 分析问题，明确要做什么
  2. 搜索   : Grep 搜索 Skills/Wiki
     Grep '关键词' ~/.agent-flow/skills/ 和 .agent-flow/skills/
     Grep '关键词' ~/.agent-flow/wiki/pitfalls/
  3. 确认   : 找到 Skill → 按 Procedure；未找到 → 询问用户
  {UNBLOCK_SUFFIX}

搜索完成后按思维链继续执行：
  4. 执行   : 按方案执行操作
  5. 验证   : 检查是否解决
  6. 未解决 → 回到步骤 1（禁止推测）"""


def get_max_search_age(project_root) -> int:
    """根据复杂度获取搜索标记有效期"""
    level = get_complexity_level(project_root)
    return MAX_SEARCH_AGE_MAP.get(level, DEFAULT_MAX_SEARCH_AGE)


def is_code_file(file_path: str) -> bool:
    """判断是否为代码文件（需要搜索标记）"""
    for prefix in ALLOWED_PATH_PREFIXES:
        if prefix in file_path:
            return False
    _, ext = os.path.splitext(file_path)
    if ext.lower() in (".md", ".txt", ".rst", ".adoc"):
        return False
    if ext.lower() in CODE_EXTENSIONS:
        return True
    if os.path.basename(file_path) in CODE_FILENAMES:
        return True
    return False


def is_readonly_bash(command: str) -> bool:
    """判断 Bash 命令是否为只读（不需要搜索标记）"""
    cmd = command.strip()
    for prefix in READONLY_BASH_PREFIXES:
        if cmd.startswith(prefix):
            return True
    return False


def has_recent_search(marker_file, project_root) -> bool:
    """检查是否有近期的搜索标记（根据复杂度调整有效期）"""
    if not os.path.isfile(marker_file):
        return False
    try:
        mtime = os.path.getmtime(marker_file)
        age = time.time() - mtime
        max_age = get_max_search_age(project_root)
        return age < max_age
    except Exception:
        return False


def main():
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    # 低复杂度任务不需要思维链强制检查
    complexity = get_complexity_level(project_root)
    if complexity == "simple":
        sys.exit(0)

    phase_file = read_state_path(project_root, "current_phase.md")
    phase_found = os.path.isfile(phase_file) and os.path.getsize(phase_file) > 10
    if not phase_found:
        sys.exit(0)

    # 读取 hook 输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    needs_search_check = False
    target_desc = ""

    # Write/Edit: 代码文件需要搜索标记
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if is_code_file(file_path):
            needs_search_check = True
            target_desc = f"文件: {file_path}"

    # Bash: 非只读命令需要搜索标记
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if not is_readonly_bash(command):
            needs_search_check = True
            target_desc = f"命令: {command[:80]}"

    if not needs_search_check:
        sys.exit(0)

    # 检查搜索标记
    marker_file = read_state_path(project_root, ".search-done")
    if has_recent_search(marker_file, project_root):
        sys.exit(0)  # 搜索已做，允许执行

    # 无搜索标记 → 硬阻断（simple 已在 main() 顶部跳过）
    record_violation()
    print(f"{CHAIN_PROMPT}\n目标: {target_desc}")
    sys.exit(2)


if __name__ == "__main__":
    main()
