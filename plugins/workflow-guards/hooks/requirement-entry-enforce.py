#!/usr/bin/env python3
"""Block code changes until requirement-entry prerequisites are completed."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from contract_utils import NO_RETRY_LINE, UNBLOCK_SUFFIX, is_readonly_bash

STATE_FILE = ".claude/.requirement-entry-state.json"

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


def _find_repo_root() -> Path | None:
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _load_state(state_path: Path) -> dict | None:
    if not state_path.is_file():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _is_allowed_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return (
        normalized.startswith(".agent-flow/")
        or normalized.startswith(".claude/")
        or "/.agent-flow/" in normalized
        or "/.claude/" in normalized
    )


def _is_code_file(file_path: str) -> bool:
    if _is_allowed_path(file_path):
        return False
    suffix = os.path.splitext(file_path)[1].lower()
    if suffix in CODE_EXTENSIONS:
        return True
    return os.path.basename(file_path) in CODE_FILENAMES


def _block_message(state: dict, target: str) -> str:
    claude_md = state.get("claude_md") or "CLAUDE.md"
    fewshots = state.get("fewshots") or "fewshots/*.md"
    lines = [
        "[AgentFlow BLOCKED] requirement-entry 强制流程未完成，禁止继续执行可变更操作。",
        NO_RETRY_LINE,
        "",
        f"目标: {target}",
        "",
        "✅ 解除方法：",
    ]
    if not state.get("claude_md_read"):
        lines.append(f"  1. 先阅读 `{claude_md}`")
    if state.get("fewshots_exists") and not state.get("fewshots_read"):
        lines.append(f"  2. 先阅读 `{fewshots}`")
    if not state.get("agent_flow_ready"):
        lines.append("  3. 确保当前项目已完成 `agent-flow init`")
    lines.append("  4. 完成后再进入 pre-flight / 需求拆解 / 实现")
    lines.append(f"  {UNBLOCK_SUFFIX}")
    return "\n".join(lines)


def main() -> None:
    repo_root = _find_repo_root()
    if repo_root is None:
        sys.exit(0)
    state = _load_state(repo_root / STATE_FILE)
    if not state or state.get("status") == "ready":
        sys.exit(0)

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    if tool_name in {"Write", "Edit", "MultiEdit"}:
        file_path = str(tool_input.get("file_path", ""))
        if file_path and _is_code_file(file_path):
            print(_block_message(state, file_path), file=sys.stderr)
            sys.exit(2)
        sys.exit(0)

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if is_readonly_bash(command):
            sys.exit(0)
        if command.startswith("agent-flow init"):
            sys.exit(0)
        print(_block_message(state, command[:120]), file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
