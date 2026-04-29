#!/usr/bin/env python3
"""
AgentFlow Thinking Chain Enforcer — PreToolUse hook.
对中高复杂度任务强制执行“先搜索再修改/执行”。
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from contract_utils import (
    NO_RETRY_LINE,
    UNBLOCK_SUFFIX,
    find_project_root,
    get_complexity_level,
    has_shared_search_session,
    is_simple_string_replacement,
    read_state_path,
    touch_shared_search_session,
)

MAX_SEARCH_AGE_MAP = {
    "medium": 900,
    "complex": 600,
}
DEFAULT_MAX_SEARCH_AGE = 900

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
    "agent-flow",
    "python3",
    "python",
    "node",
    ".venv/bin/python",
    "pytest",
    ".venv/bin/pytest",
    ".venv/bin/python -m pytest",
    "npx tsx",
    "npx",
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
    "curl",
)

LARK_SAFE_PREFIXES = (
    "lark-cli schema ",
    "lark-cli --help",
    "lark-cli help",
    "lark-cli --version",
    "lark-cli doctor",
    "lark-cli auth ",
)

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


def get_max_search_age(project_root: Path) -> int:
    return MAX_SEARCH_AGE_MAP.get(get_complexity_level(project_root), DEFAULT_MAX_SEARCH_AGE)


def _is_allowed_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return (
        normalized.startswith(".agent-flow/")
        or normalized.startswith(".claude/")
        or "/.agent-flow/" in normalized
        or "/.claude/" in normalized
    )


def is_code_file(file_path: str) -> bool:
    if _is_allowed_path(file_path):
        return False
    suffix = os.path.splitext(file_path)[1].lower()
    if suffix in {".md", ".txt", ".rst", ".adoc"}:
        return False
    if suffix in CODE_EXTENSIONS:
        return True
    return os.path.basename(file_path) in CODE_FILENAMES


def is_readonly_bash(command: str) -> bool:
    cmd = command.strip()
    if any(cmd.startswith(prefix) for prefix in LARK_SAFE_PREFIXES):
        return True
    return any(cmd.startswith(prefix) for prefix in READONLY_BASH_PREFIXES)


def has_recent_search(marker_file: Path, project_root: Path) -> bool:
    if not marker_file.is_file():
        return False
    try:
        age = time.time() - marker_file.stat().st_mtime
    except OSError:
        return False
    return age < get_max_search_age(project_root)


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    if get_complexity_level(project_root) == "simple":
        sys.exit(0)

    phase_file = read_state_path(project_root, "current_phase.md")
    if not phase_file.is_file() or phase_file.stat().st_size <= 10:
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    needs_search_check = False
    target_desc = ""

    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if is_code_file(file_path):
            needs_search_check = True
            target_desc = f"文件: {file_path}"
    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        if not is_readonly_bash(command):
            needs_search_check = True
            target_desc = f"命令: {command[:80]}"

    if not needs_search_check:
        sys.exit(0)

    if is_simple_string_replacement(project_root, tool_name, tool_input):
        sys.exit(0)

    operation_type = "bash_exec" if tool_name == "Bash" else "code_edit"
    marker_file = read_state_path(project_root, ".search-done")
    if has_recent_search(marker_file, project_root):
        touch_shared_search_session(project_root, operation_type)
        sys.exit(0)

    complexity = get_complexity_level(project_root)
    if has_shared_search_session(project_root, operation_type, complexity):
        touch_shared_search_session(project_root, operation_type)
        sys.exit(0)

    print(f"{CHAIN_PROMPT}\n目标: {target_desc}")
    sys.exit(2)


if __name__ == "__main__":
    main()
