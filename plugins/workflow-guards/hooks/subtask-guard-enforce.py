#!/usr/bin/env python3
"""
AgentFlow Subtask Guard Enforcer — PreToolUse hook.
强制执行 subtask-guard：每次代码修改前检查是否执行了子任务搜索守卫。
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

MAX_AGE_MAP = {
    "medium": 1800,
    "complex": 1200,
}
DEFAULT_MAX_AGE = 1800

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

GUARD_PROMPT = f"""[AgentFlow BLOCKED] Subtask-guard 未执行 — 你没有在修改代码前搜索知识库！

{NO_RETRY_LINE}

✅ 解除方法：完成以下任一方案后，当前操作会自动放行：

  方案 A: 快速搜索（推荐，1步即可解除）
    Grep "{{关键词}}" .agent-flow/skills/ 或 ~/.agent-flow/skills/
    搜索后标记自动创建

  方案 B: 完整 subtask-guard 流程（新子任务时使用）
    1. Grep "{{关键词}}" .agent-flow/skills/
    2. Grep "{{关键词}}" ~/.agent-flow/skills/
    3. Grep "{{关键词}}" .agent-flow/memory/main/Soul.md
    4. Grep "{{关键词}}" .agent-flow/wiki/ + 全局wiki

  方案 C: 跨会话误触，执行任意搜索即可重置
    Grep "subtask" .agent-flow/

  {UNBLOCK_SUFFIX}
  标记有效期：Medium 30min / Complex 20min"""


def get_max_age(project_root: Path) -> int:
    return MAX_AGE_MAP.get(get_complexity_level(project_root), DEFAULT_MAX_AGE)


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


def has_valid_guard(project_root: Path) -> bool:
    max_age = get_max_age(project_root)
    markers = [
        read_state_path(project_root, ".subtask-guard-done"),
        read_state_path(project_root, ".search-done"),
    ]
    for marker in markers:
        if not marker.is_file():
            continue
        try:
            age = time.time() - marker.stat().st_mtime
        except OSError:
            continue
        if age < max_age:
            return True
    return False


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

    if input_data.get("tool_name", "") not in ("Write", "Edit"):
        sys.exit(0)
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path or not is_code_file(file_path):
        sys.exit(0)

    if is_simple_string_replacement(project_root, tool_name, tool_input):
        sys.exit(0)

    if has_valid_guard(project_root):
        touch_shared_search_session(project_root, "code_edit")
        sys.exit(0)

    complexity = get_complexity_level(project_root)
    if has_shared_search_session(project_root, "code_edit", complexity):
        touch_shared_search_session(project_root, "code_edit")
        sys.exit(0)

    print(f"{GUARD_PROMPT}\n目标文件: {file_path}")
    sys.exit(2)


if __name__ == "__main__":
    main()
