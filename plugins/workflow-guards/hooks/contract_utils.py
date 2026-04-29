#!/usr/bin/env python3
"""Shared AgentFlow hook helpers for state-contract compatibility."""

from __future__ import annotations

import json
import os
import shlex
import shutil
from pathlib import Path

CANONICAL_PLAN_HEADERS = [
    "# 任务:",
    "## 复杂度",
    "## RPI 阶段规划",
    "## 实施计划",
    "## 变更点",
    "## 验收标准",
]

LEGACY_PLAN_MARKERS = [
    "## Implementation Plan",
    "## 实施计划",
    "## 变更点",
    "## CP",
    "## 代码修改",
    "## 代码影响",
    "### Change Points",
    "### Change Points (Updated)",
]


def find_project_root(start: str | None = None) -> Path | None:
    current = Path(start or os.getcwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".agent-flow").exists():
            return candidate
    return None


def get_state_dir(project_root: Path) -> Path:
    return project_root / ".agent-flow" / "state"


def read_state_path(project_root: Path, filename: str) -> Path:
    return get_state_dir(project_root) / filename


def write_state_path(project_root: Path, filename: str) -> Path:
    state_dir = get_state_dir(project_root)
    return state_dir / filename


def detect_plan_format(content: str) -> str:
    if all(header in content for header in CANONICAL_PLAN_HEADERS):
        return "canonical"
    if any(marker in content for marker in LEGACY_PLAN_MARKERS):
        return "legacy"
    return "none"


def has_implementation_plan(project_root: Path) -> tuple[bool, str | None]:
    phase_path = read_state_path(project_root, "current_phase.md")
    if not phase_path.is_file():
        return False, None
    try:
        content = phase_path.read_text(encoding="utf-8")
    except OSError:
        return False, None
    plan_format = detect_plan_format(content)
    return plan_format in {"canonical", "legacy"}, plan_format if plan_format != "none" else None


def get_complexity_level(project_root: Path) -> str:
    complexity_path = read_state_path(project_root, ".complexity-level")
    if not complexity_path.is_file():
        return "medium"
    try:
        for line in complexity_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("level="):
                level = stripped.split("=", 1)[1].strip().lower()
                if level in ("simple", "medium", "complex"):
                    return level
    except OSError:
        pass
    return "medium"


def load_marker_entries(path: Path) -> list[dict[str, str]]:
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
            continue
        key, value = stripped.split("=", 1)
        current[key.strip()] = value.strip()
    if current:
        entries.append(current)
    return entries


# ---- Shared BLOCKED-message constants ----
NO_RETRY_LINE = "⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。"
UNBLOCK_SUFFIX = "完成后，当前操作会自动放行。"


def structured_marker_exists(path: Path, required: tuple[str, ...]) -> bool:
    for entry in load_marker_entries(path):
        if all(entry.get(key, "").strip() for key in required):
            return True
    return False


# ---- Shared code-change detection helpers ----

CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".kt",
    ".swift", ".m", ".h", ".c", ".cpp", ".rb", ".php", ".vue", ".svelte",
    ".css", ".scss", ".less", ".html", ".sql", ".graphql", ".sh", ".bash", ".zsh",
}

CODE_FILENAMES = {
    "package.json", "tsconfig.json", "Makefile", "Dockerfile", "Podfile", "Gemfile",
    "build.gradle", "settings.gradle", "app.json", "babel.config.js", "metro.config.js",
}

ALLOWED_PATH_PREFIXES = (".agent-flow", ".claude")

READONLY_BASH_PREFIXES = (
    "ls", "cat", "head", "tail", "find", "grep", "rg", "wc", "which", "pwd", "whoami",
    "uname", "env", "printenv", "echo", "type ", "command ", "git status", "git log",
    "git diff", "git branch", "git remote", "git rev-parse", "git show",
)


def is_code_file(file_path: str) -> bool:
    for prefix in ALLOWED_PATH_PREFIXES:
        if prefix in file_path:
            return False
    _, ext = os.path.splitext(file_path)
    if ext.lower() in CODE_EXTENSIONS:
        return True
    return os.path.basename(file_path) in CODE_FILENAMES


def is_readonly_bash(command: str) -> bool:
    cmd = command.strip()
    return any(cmd.startswith(prefix) for prefix in READONLY_BASH_PREFIXES)


# ---- Hook / tool readiness helpers ----

def has_agent_flow_hooks(project_root: Path) -> bool:
    """Check whether .claude/settings*.json registers any agent-flow hooks."""
    for settings in [project_root / ".claude" / "settings.local.json", project_root / ".claude" / "settings.json"]:
        if not settings.is_file():
            continue
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except Exception:
            continue
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            continue
        text = json.dumps(hooks, ensure_ascii=False).lower()
        if "agent-flow" in text or "agent_flow" in text:
            return True
    return False


def agent_flow_hook_registration_status(project_root: Path) -> tuple[bool, list[str]]:
    """Return (ok, missing_paths) for agent-flow hook command registrations."""
    missing: list[str] = []
    has_registration = False
    settings_files = [project_root / ".claude" / "settings.local.json", project_root / ".claude" / "settings.json"]

    for settings in settings_files:
        if not settings.is_file():
            continue
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except Exception:
            continue
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            continue
        for event_entries in hooks.values():
            if not isinstance(event_entries, list):
                continue
            for entry in event_entries:
                if not isinstance(entry, dict):
                    continue
                for hook in entry.get("hooks", []):
                    if not isinstance(hook, dict) or hook.get("type") != "command":
                        continue
                    command = str(hook.get("command", "")).strip()
                    lowered = command.lower()
                    if "agent-flow" not in lowered and "agent_flow" not in lowered:
                        continue
                    has_registration = True
                    parts = shlex.split(command)
                    if len(parts) < 2:
                        continue
                    script = parts[1]
                    script_path = Path(script)
                    if not script_path.is_absolute():
                        script_path = (project_root / script_path).resolve()
                    if not script_path.exists():
                        missing.append(str(script_path))

    if not has_registration:
        return False, []
    return len(missing) == 0, sorted(set(missing))


def is_cli_available(cli_name: str) -> bool:
    """Check whether a CLI tool is on the current PATH."""
    return shutil.which(cli_name) is not None
