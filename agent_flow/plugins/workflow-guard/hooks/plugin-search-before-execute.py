#!/usr/bin/env python3
"""workflow-guard: block execute actions until search evidence exists."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

NO_RETRY_LINE = "⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。"
UNBLOCK_SUFFIX = "完成后，当前操作会自动放行。"
MAX_AGE_SECONDS = 1800

MARKERS = (
    ".agent-flow/state/.plugin-search-done",
    ".agent-flow/state/.search-done",
)
CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".kt",
    ".swift", ".m", ".h", ".c", ".cpp", ".rb", ".php", ".vue", ".svelte",
    ".css", ".scss", ".less", ".html", ".sql", ".graphql", ".sh", ".bash", ".zsh",
}
CODE_FILENAMES = {
    "package.json", "tsconfig.json", "Makefile", "Dockerfile", "Podfile", "Gemfile",
    "build.gradle", "settings.gradle", "app.json", "babel.config.js", "metro.config.js",
}
ALLOWED_PATH_PREFIXES = (".agent-flow", ".dev-workflow", ".claude")
READONLY_BASH_PREFIXES = (
    "ls", "cat", "head", "tail", "find", "grep", "rg", "wc", "which", "pwd", "whoami",
    "uname", "env", "printenv", "echo", "type ", "command ", "git status", "git log",
    "git diff", "git branch", "git remote", "git rev-parse", "git show",
)


def _find_project_root() -> Path | None:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".agent-flow").exists() or (candidate / ".dev-workflow").exists():
            return candidate
    return None


def _has_recent_search(project_root: Path) -> bool:
    now = time.time()
    for rel in MARKERS:
        marker = project_root / rel
        if marker.is_file() and now - marker.stat().st_mtime <= MAX_AGE_SECONDS:
            return True
    return False


def _is_code_file(file_path: str) -> bool:
    for prefix in ALLOWED_PATH_PREFIXES:
        if prefix in file_path:
            return False
    _, ext = os.path.splitext(file_path)
    if ext.lower() in CODE_EXTENSIONS:
        return True
    return os.path.basename(file_path) in CODE_FILENAMES


def _is_readonly_bash(command: str) -> bool:
    cmd = command.strip()
    return any(cmd.startswith(prefix) for prefix in READONLY_BASH_PREFIXES)


def _block(target: str) -> None:
    print(
        "[workflow-guard BLOCKED] 先搜索再执行：未检测到近期搜索证据。\n"
        f"{NO_RETRY_LINE}\n\n"
        "✅ 解除方法：\n"
        "  1. 先检索项目/团队 skill 或 wiki\n"
        "  2. 再执行实现或变更命令\n"
        f"  目标: {target}\n"
        f"  {UNBLOCK_SUFFIX}"
    )


def main() -> None:
    project_root = _find_project_root()
    if project_root is None:
        sys.exit(0)

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    if _has_recent_search(project_root):
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name in {"Write", "Edit", "MultiEdit"}:
        file_path = str(tool_input.get("file_path", ""))
        if _is_code_file(file_path):
            _block(file_path)
            sys.exit(2)
        sys.exit(0)

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if _is_readonly_bash(command):
            sys.exit(0)
        _block(command[:120])
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
