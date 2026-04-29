#!/usr/bin/env python3
"""Enforce Jira workflow prerequisites and field governance.

PreToolUse guard for Bash jira commands:
1) Jira create/subtask/transition/comment requires Jira-context marker.
2) Non-default customfield usage requires explicit field-decision marker.
3) Placeholder/random values are forbidden.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import find_project_root, load_marker_entries, read_state_path

NO_RETRY_LINE = "⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。"
UNBLOCK_SUFFIX = "完成后，当前操作会自动放行。"

JIRA_CONTEXT_MARKER = ".jira-context-ready"
JIRA_FIELD_DECISION_MARKER = ".jira-field-decision-confirmed"
MARKER_MAX_AGE = 7200

ALLOWED_DEFAULT_CUSTOMFIELDS = {
    "11001",  # 需求目标=OKR相关
    "11121",  # 开发预估工期=8
    "11154",  # 是否需要评审
    "11315",  # 评审策略
    "11157",  # 模块域
    "11000",  # 需求文档链接
    "11114",  # 相关角色
    "10013",  # platform (部分实例)
}

PLACEHOLDER_PATTERNS = (
    "xxx",
    "todo",
    "tmp",
    "test",
    "随便",
    "待定",
    "unknown",
)


FIELD_RE = re.compile(r"--field\s+([^\s]+)")
CUSTOMFIELD_RE = re.compile(r"customfield_(\d+)=(.*)")


def _has_recent_marker(path: Path, max_age: int = MARKER_MAX_AGE) -> bool:
    if not path.is_file():
        return False
    now = time.time()
    if now - path.stat().st_mtime > max_age:
        return False
    entries = load_marker_entries(path)
    if not entries:
        return path.stat().st_size > 0
    for entry in entries:
        status = str(entry.get("status", "")).strip().lower()
        if status in {"ready", "confirmed", "done", "resolved"}:
            return True
    return False


def _extract_fields(command: str) -> list[str]:
    return FIELD_RE.findall(command)


def _has_placeholder_value(command: str) -> bool:
    lower = command.lower()
    return any(token in lower for token in PLACEHOLDER_PATTERNS)


def _unknown_customfields(command: str) -> set[str]:
    unknown: set[str] = set()
    for field_expr in _extract_fields(command):
        m = CUSTOMFIELD_RE.match(field_expr)
        if not m:
            continue
        field_id = m.group(1)
        if field_id not in ALLOWED_DEFAULT_CUSTOMFIELDS:
            unknown.add(field_id)
    return unknown


def _is_jira_mutation(command: str) -> bool:
    cmd = command.strip()
    return (
        cmd.startswith("jira issue create")
        or cmd.startswith("jira issue subtask")
        or cmd.startswith("jira issue transition")
        or cmd.startswith("jira issue comment")
        or cmd.startswith("jira issue update")
    )


def _block(message: str) -> None:
    print(
        f"[AgentFlow BLOCKED] {message}\n"
        f"{NO_RETRY_LINE}\n\n"
        "✅ 解除方法：\n"
        "  1. 先读取 Jira 相关 wiki/skill（jira.md / mai-jira-cli.md / jira-search-to-dev）\n"
        "  2. 若使用非默认字段，必须先获得用户确认并写入 .jira-field-decision-confirmed\n"
        f"  {UNBLOCK_SUFFIX}",
        file=sys.stderr,
    )


def _session_cookie_exists() -> bool:
    candidates = [
        Path.home() / ".jira" / "cookies.json",
        Path.home() / ".jira" / "session.json",
        Path.home() / ".config" / "jira" / "cookies.json",
    ]
    env_cookie = os.environ.get("JIRA_COOKIE_FILE", "").strip()
    if env_cookie:
        candidates.append(Path(env_cookie).expanduser())
    return any(path.is_file() and path.stat().st_size > 0 for path in candidates)


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    command = str(payload.get("tool_input", {}).get("command", "")).strip()
    if not command.startswith("jira"):
        sys.exit(0)

    if command.startswith("jira auth login") and _session_cookie_exists():
        _block("检测到本地已有 Jira cookie/session，请先复用会话：执行 `jira auth status`，确认失效后再登录。")
        sys.exit(2)

    if not _is_jira_mutation(command):
        sys.exit(0)

    context_marker = read_state_path(project_root, JIRA_CONTEXT_MARKER)
    if not _has_recent_marker(context_marker):
        _block("Jira 操作前置阅读证据缺失（.jira-context-ready 不存在或过期）")
        sys.exit(2)

    if _has_placeholder_value(command):
        _block("检测到疑似占位/随意字段值，禁止提交")
        sys.exit(2)

    unknown_fields = _unknown_customfields(command)
    if unknown_fields:
        decision_marker = read_state_path(project_root, JIRA_FIELD_DECISION_MARKER)
        if not _has_recent_marker(decision_marker):
            _block(
                "检测到非默认 Jira 字段 customfield_"
                + ", customfield_".join(sorted(unknown_fields))
                + "，缺少用户确认标记"
            )
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
