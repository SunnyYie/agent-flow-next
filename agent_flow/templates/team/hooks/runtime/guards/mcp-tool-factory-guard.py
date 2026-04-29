#!/usr/bin/env python3
"""Block MCP server creation/config changes until user approval is resolved.

Triggered on PreToolUse. If `.mcp-tool-factory-requested` contains unresolved
entries, MCP expansion actions are blocked until user approval is recorded.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

NO_RETRY_LINE = "⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。"
UNBLOCK_SUFFIX = "完成后，当前操作会自动放行。"
MARKER_NAME = ".mcp-tool-factory-requested"

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

MCP_BASH_SIGNALS = (
    ".mcp.json",
    "agent_flow.mcp.server",
    "/mcp/",
    " mcp ",
    "mcp server",
    "modelcontextprotocol",
)


def _find_project_root() -> Path | None:
    cwd = Path.cwd().resolve()
    candidates = [candidate for candidate in [cwd, *cwd.parents] if (candidate / ".agent-flow").exists()]
    if not candidates:
        return None
    git_root: Path | None = None
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            git_root = Path(proc.stdout.strip()).resolve()
    except OSError:
        git_root = None
    if git_root is None:
        for candidate in [cwd, *cwd.parents]:
            if (candidate / ".git").exists():
                git_root = candidate
                break
    if git_root is not None:
        if (git_root / ".agent-flow").exists():
            return git_root
        in_repo = [c for c in candidates if git_root == c or git_root in c.parents]
        if in_repo:
            return in_repo[-1]
    return candidates[0]


def _state_marker_path(project_root: Path) -> Path:
    return project_root / ".agent-flow" / "state" / MARKER_NAME


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
        if "=" not in stripped:
            current["_raw"] = stripped
            continue
        key, value = stripped.split("=", 1)
        current[key.strip()] = value.strip()
    if current:
        entries.append(current)
    return entries


def _entry_resolved(entry: dict[str, str]) -> bool:
    status = entry.get("status", "").strip().lower()
    if status in {"resolved", "closed", "done", "approved", "confirmed", "rejected", "declined", "cancelled"}:
        return True
    resolved = entry.get("resolved", "").strip().lower()
    return resolved in {"1", "true", "yes", "y"}


def _has_pending_request(marker_path: Path) -> bool:
    if not marker_path.is_file():
        return False
    entries = _load_marker_entries(marker_path)
    if not entries:
        return marker_path.stat().st_size > 0
    return any(not _entry_resolved(entry) for entry in entries)


def _is_mcp_sensitive_file(file_path: str) -> bool:
    normalized = os.path.normpath(file_path).replace("\\", "/").lower()
    if normalized.endswith("/.mcp.json") or normalized == ".mcp.json":
        return True
    if "/mcp/" in normalized:
        return True
    return normalized.endswith("-mcp.json")


def _is_readonly_bash(command: str) -> bool:
    cmd = command.strip()
    return any(cmd.startswith(prefix) for prefix in READONLY_BASH_PREFIXES)


def _is_mcp_sensitive_bash(command: str) -> bool:
    text = f" {command.strip().lower()} "
    return any(signal in text for signal in MCP_BASH_SIGNALS)


def _print_blocked(reason: str, marker_path: Path, target: str = "") -> None:
    print(
        "[AgentFlow BLOCKED] MCP 工具工厂提案尚未完成审批，禁止创建/修改 MCP 能力。\n"
        f"{NO_RETRY_LINE}\n\n"
        "待处理标记: "
        f"{marker_path}\n"
        f"阻断原因: {reason}\n"
        f"{('目标: ' + target + chr(10)) if target else ''}"
        "\n✅ 解除方法：\n"
        "  1. 向用户展示 MCP 提案（Problem/Scope/Security/Validation/Rollback）\n"
        "  2. 获得用户明确“同意创建”的确认\n"
        f"  3. 将 {MARKER_NAME} 标记更新为 approved/resolved 或清空未决项\n"
        f"  {UNBLOCK_SUFFIX}"
    )


def main() -> None:
    project_root = _find_project_root()
    if project_root is None:
        sys.exit(0)

    marker_path = _state_marker_path(project_root)
    if not _has_pending_request(marker_path):
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
        if file_path and _is_mcp_sensitive_file(file_path):
            _print_blocked("尝试修改 MCP 配置或 MCP 相关代码目录", marker_path, file_path)
            sys.exit(2)
        sys.exit(0)

    if tool_name == "Bash":
        command = tool_input.get("command", "")
        if _is_readonly_bash(command):
            sys.exit(0)
        if _is_mcp_sensitive_bash(command):
            _print_blocked("尝试执行 MCP 创建/安装/配置相关命令", marker_path, command[:120])
            sys.exit(2)
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
