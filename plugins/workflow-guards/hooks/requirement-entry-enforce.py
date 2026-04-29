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


def _request_context_path(repo_root: Path, state: dict) -> Path:
    path = str(state.get("request_context", "")).strip()
    if path:
        return Path(path)
    return repo_root / ".agent-flow" / "state" / "request-context.json"


def _load_request_context(repo_root: Path, state: dict) -> dict:
    path = _request_context_path(repo_root, state)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _task_list_ready(repo_root: Path) -> bool:
    task_list = repo_root / ".agent-flow" / "state" / "task-list.md"
    if not task_list.is_file():
        return False
    try:
        content = task_list.read_text(encoding="utf-8")
    except OSError:
        return False
    return len(content.strip()) > 0


def _post_ready_blockers(repo_root: Path, state: dict, target: str) -> str | None:
    if state.get("claude_md_exists") and not state.get("claude_project_rules_ready", True):
        return (
            "[AgentFlow BLOCKED] 当前项目的 CLAUDE.md 缺少项目结构/任务清单/Agent 分工等开发规范，"
            "禁止直接进入开发。\n"
            f"{NO_RETRY_LINE}\n\n"
            "✅ 解除方法：\n"
            "  1. 补充 CLAUDE.md 中的项目结构、任务清单、Agent 分工规范\n"
            "  2. 重新阅读 CLAUDE.md\n"
            f"  {UNBLOCK_SUFFIX}\n"
            f"目标: {target}"
        )

    if not _task_list_ready(repo_root):
        return (
            "[AgentFlow BLOCKED] 需求任务清单未完成，禁止继续执行可变更操作。\n"
            f"{NO_RETRY_LINE}\n\n"
            "✅ 解除方法：\n"
            "  1. 完善 `.agent-flow/state/task-list.md`\n"
            "  2. 为每个任务补充功能点、目标文件/模块、依赖、验收方式\n"
            f"  {UNBLOCK_SUFFIX}\n"
            f"目标: {target}"
        )

    request_context = _load_request_context(repo_root, state)
    if request_context.get("ui_constraints_required"):
        ui_marker = repo_root / ".agent-flow" / "state" / ".ui-design-guided"
        if not ui_marker.is_file():
            return (
                "[AgentFlow BLOCKED] 当前请求包含 UI 文件，必须先按 UI 规范完成设计约束确认。\n"
                f"{NO_RETRY_LINE}\n\n"
                "✅ 解除方法：\n"
                "  1. 严格阅读并对齐 UI file 的设计规范\n"
                "  2. 使用 frontend-design 插件与 ui-ux-pro-max skill 完成设计约束确认\n"
                "  3. 写入 `.agent-flow/state/.ui-design-guided`\n"
                f"  {UNBLOCK_SUFFIX}\n"
                f"目标: {target}"
            )
    return None


def main() -> None:
    repo_root = _find_repo_root()
    if repo_root is None:
        sys.exit(0)
    state = _load_state(repo_root / STATE_FILE)
    if not state:
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
            if state.get("status") == "ready":
                blocker = _post_ready_blockers(repo_root, state, file_path)
                if blocker:
                    print(blocker, file=sys.stderr)
                    sys.exit(2)
                sys.exit(0)
            print(_block_message(state, file_path), file=sys.stderr)
            sys.exit(2)
        sys.exit(0)

    if tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        if is_readonly_bash(command):
            sys.exit(0)
        if command.startswith("agent-flow init"):
            sys.exit(0)
        if state.get("status") == "ready":
            blocker = _post_ready_blockers(repo_root, state, command[:120])
            if blocker:
                print(blocker, file=sys.stderr)
                sys.exit(2)
            sys.exit(0)
        print(_block_message(state, command[:120]), file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
