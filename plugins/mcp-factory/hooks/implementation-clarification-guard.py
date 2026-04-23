#!/usr/bin/env python3
"""Block implementation actions when clarification is pending.

Triggered on PreToolUse. If `.implementation-question-raised` indicates an
unresolved clarification item, code-changing actions are blocked until user
confirmation is captured and the marker is resolved/cleared.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

NO_RETRY_LINE = "⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。"
UNBLOCK_SUFFIX = "完成后，当前操作会自动放行。"
MARKER_NAME = ".implementation-question-raised"

ALWAYS_ALLOWED_TOOLS = {
    "Read",
    "Glob",
    "Grep",
    "Agent",
    "AskUserQuestion",
    "TodoWrite",
    "WebSearch",
    "Skill",
    "EnterPlanMode",
    "ExitPlanMode",
    "ScheduleWakeup",
    "CronList",
    "CronDelete",
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
)

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
}

STATE_ALLOWED_PREFIXES = (".agent-flow/state", ".dev-workflow/state")
DOC_ALLOWED_EXTENSIONS = {".md", ".txt", ".rst", ".adoc", ".yaml", ".yml", ".json"}


def _find_project_root() -> Path | None:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".agent-flow").exists() or (candidate / ".dev-workflow").exists():
            return candidate
    return None


def _state_marker_path(project_root: Path) -> Path:
    canonical = project_root / ".agent-flow" / "state" / MARKER_NAME
    legacy = project_root / ".dev-workflow" / "state" / MARKER_NAME
    if canonical.is_file():
        return canonical
    if legacy.is_file():
        return legacy
    return canonical


def _load_marker_entries(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not raw:
        return []

    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                entries.append(current)
                current = {}
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            current[key.strip()] = value.strip()
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            current[key.strip()] = value.strip()
            continue
        else:
            current["_raw"] = stripped
            continue
    if current:
        entries.append(current)
    return entries


def _entry_resolved(entry: dict[str, str]) -> bool:
    status = entry.get("status", "").strip().lower()
    if status in {"resolved", "closed", "done", "confirmed"}:
        return True
    resolved = entry.get("resolved", "").strip().lower()
    return resolved in {"1", "true", "yes", "y"}


def _has_pending_clarification(marker_path: Path) -> bool:
    if not marker_path.is_file():
        return False
    entries = _load_marker_entries(marker_path)
    if not entries:
        return marker_path.stat().st_size > 0
    return any(not _entry_resolved(entry) for entry in entries)


def _is_code_file(file_path: str) -> bool:
    _, ext = os.path.splitext(file_path)
    if ext.lower() in CODE_EXTENSIONS:
        return True
    return os.path.basename(file_path) in CODE_FILENAMES


def _is_state_doc(file_path: str) -> bool:
    normalized = os.path.normpath(file_path).replace("\\", "/")
    if any(prefix in normalized for prefix in STATE_ALLOWED_PREFIXES):
        return True
    _, ext = os.path.splitext(normalized)
    return ext.lower() in DOC_ALLOWED_EXTENSIONS and (
        "/.agent-flow/" in normalized or "/.dev-workflow/" in normalized
    )


def _is_readonly_bash(command: str) -> bool:
    cmd = command.strip()
    return any(cmd.startswith(prefix) for prefix in READONLY_BASH_PREFIXES)


def _print_blocked(reason: str, marker_path: Path, target: str = "") -> None:
    print(
        "[AgentFlow BLOCKED] 实现期存在待澄清事项，禁止继续实施。\n"
        f"{NO_RETRY_LINE}\n\n"
        "待处理标记: "
        f"{marker_path}\n"
        f"阻断原因: {reason}\n"
        f"{('目标: ' + target + chr(10)) if target else ''}"
        "\n✅ 解除方法：\n"
        "  1. 向用户确认实现期问题（范围/语义/兼容策略/冲突点）\n"
        "  2. 在 `current_phase.md` 更新“实现期待确认事项”并写明确认结论\n"
        f"  3. 将 {MARKER_NAME} 标记更新为 resolved 或清空未决项\n"
        f"  {UNBLOCK_SUFFIX}"
    )


def main() -> None:
    project_root = _find_project_root()
    if project_root is None:
        sys.exit(0)

    marker_path = _state_marker_path(project_root)
    if not _has_pending_clarification(marker_path):
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name in ALWAYS_ALLOWED_TOOLS:
        sys.exit(0)

    if tool_name in {"Write", "Edit", "MultiEdit"}:
        file_path = tool_input.get("file_path", "")
        if not file_path:
            sys.exit(0)
        if _is_state_doc(file_path):
            sys.exit(0)
        if _is_code_file(file_path):
            _print_blocked("尝试修改代码文件", marker_path, file_path)
            sys.exit(2)
        sys.exit(0)

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if _is_readonly_bash(command):
            sys.exit(0)
        _print_blocked("尝试执行可能改变状态的命令", marker_path, command[:120])
        sys.exit(2)

    if tool_name == "NotebookEdit":
        _print_blocked("尝试编辑 Notebook", marker_path)
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
