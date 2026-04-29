#!/usr/bin/env python3
"""Shared AgentFlow hook helpers for state-contract compatibility."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

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
    candidates = [candidate for candidate in [current, *current.parents] if (candidate / ".agent-flow").exists()]
    if not candidates:
        return None

    git_root: Path | None = None
    try:
        proc = subprocess.run(
            ["git", "-C", str(current), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            git_root = Path(proc.stdout.strip()).resolve()
    except OSError:
        git_root = None

    if git_root is None:
        for candidate in [current, *current.parents]:
            if (candidate / ".git").exists():
                git_root = candidate
                break

    if git_root is not None:
        root_agent_flow = git_root / ".agent-flow"
        if root_agent_flow.exists():
            return git_root
        in_repo = [c for c in candidates if git_root == c or git_root in c.parents]
        if in_repo:
            return in_repo[-1]

    return candidates[0]


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

DEFAULT_SIMPLE_REPLACE_CONFIG = {
    "enabled": True,
    "max_chars": 300,
    "max_lines": 2,
    "file_globs": ["**/*"],
    "keywords": ["cdn", "static", "asset", "image-host", "bucket"],
}

DEFAULT_SHARED_SEARCH_SESSION_CONFIG = {
    "enabled": True,
    "ttl_seconds": {
        "medium": 7200,
        "complex": 5400,
    },
}


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


def load_agent_flow_config(project_root: Path) -> dict:
    config_file = project_root / ".agent-flow" / "config.yaml"
    if not config_file.is_file():
        return {}
    try:
        content = config_file.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not content.strip():
        return {}
    if yaml is not None:
        try:
            data = yaml.safe_load(content) or {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def get_workflow_guard_config(project_root: Path) -> dict:
    config = load_agent_flow_config(project_root)
    guards = config.get("workflow_guards", {})
    return guards if isinstance(guards, dict) else {}


def get_simple_replace_config(project_root: Path) -> dict:
    user_cfg = get_workflow_guard_config(project_root).get("simple_replace_whitelist", {})
    if not isinstance(user_cfg, dict):
        user_cfg = {}
    merged = dict(DEFAULT_SIMPLE_REPLACE_CONFIG)
    merged.update(user_cfg)
    return merged


def _looks_like_url(value: str) -> bool:
    v = value.strip().strip("\"'`()")
    parsed = urlparse(v)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _url_host_swap_only(old_s: str, new_s: str) -> bool:
    old_v = old_s.strip().strip("\"'`()")
    new_v = new_s.strip().strip("\"'`()")
    if not (_looks_like_url(old_v) and _looks_like_url(new_v)):
        return False
    old_u = urlparse(old_v)
    new_u = urlparse(new_v)
    return (
        old_u.path == new_u.path
        and old_u.params == new_u.params
        and old_u.query == new_u.query
        and old_u.fragment == new_u.fragment
    )


def is_simple_string_replacement(project_root: Path, tool_name: str, tool_input: dict) -> bool:
    if tool_name != "Edit":
        return False
    cfg = get_simple_replace_config(project_root)
    if not cfg.get("enabled", True):
        return False

    file_path = str(tool_input.get("file_path", "") or "")
    old_s = str(tool_input.get("old_string", "") or "")
    new_s = str(tool_input.get("new_string", "") or "")
    if not file_path or not old_s or not new_s or old_s == new_s:
        return False

    file_globs = cfg.get("file_globs", ["**/*"])
    if isinstance(file_globs, list) and file_globs:
        if not any(fnmatch(file_path, pat) for pat in file_globs if isinstance(pat, str) and pat):
            return False

    max_chars = int(cfg.get("max_chars", 300))
    max_lines = int(cfg.get("max_lines", 2))
    if len(old_s) > max_chars or len(new_s) > max_chars:
        return False
    if old_s.count("\n") + 1 > max_lines or new_s.count("\n") + 1 > max_lines:
        return False

    keywords = [str(x).lower() for x in cfg.get("keywords", []) if isinstance(x, str)]
    combined = f"{old_s}\n{new_s}".lower()
    if keywords and any(k in combined for k in keywords):
        return True
    return _url_host_swap_only(old_s, new_s)


def get_shared_search_session_config(project_root: Path) -> dict:
    user_cfg = get_workflow_guard_config(project_root).get("shared_search_session", {})
    if not isinstance(user_cfg, dict):
        user_cfg = {}
    merged = dict(DEFAULT_SHARED_SEARCH_SESSION_CONFIG)
    merged_ttl = dict(DEFAULT_SHARED_SEARCH_SESSION_CONFIG.get("ttl_seconds", {}))
    user_ttl = user_cfg.get("ttl_seconds", {})
    if isinstance(user_ttl, dict):
        merged_ttl.update({k: v for k, v in user_ttl.items() if isinstance(v, int) and v > 0})
    merged.update(user_cfg)
    merged["ttl_seconds"] = merged_ttl
    return merged


def _shared_session_path(project_root: Path) -> Path:
    return write_state_path(project_root, ".search-shared-session.json")


def reset_shared_search_session(project_root: Path, source: str = "search") -> None:
    cfg = get_shared_search_session_config(project_root)
    if not cfg.get("enabled", True):
        return
    path = _shared_session_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    payload = {
        "source": source,
        "started_at": now,
        "last_activity_at": now,
        "last_operation_type": "",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _load_shared_session(project_root: Path) -> dict:
    path = _shared_session_path(project_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def has_shared_search_session(project_root: Path, operation_type: str, complexity: str) -> bool:
    cfg = get_shared_search_session_config(project_root)
    if not cfg.get("enabled", True):
        return False
    ttl = int(cfg.get("ttl_seconds", {}).get(complexity, 0))
    if ttl <= 0:
        return False
    session = _load_shared_session(project_root)
    if not session:
        return False
    last_activity = session.get("last_activity_at")
    if not isinstance(last_activity, (int, float)):
        return False
    if time.time() - float(last_activity) > ttl:
        return False
    last_type = str(session.get("last_operation_type", "") or "")
    return not last_type or last_type == operation_type


def touch_shared_search_session(project_root: Path, operation_type: str) -> None:
    cfg = get_shared_search_session_config(project_root)
    if not cfg.get("enabled", True):
        return
    path = _shared_session_path(project_root)
    session = _load_shared_session(project_root)
    now = time.time()
    if not session:
        session = {
            "source": "guard",
            "started_at": now,
            "last_activity_at": now,
            "last_operation_type": operation_type,
        }
    else:
        session["last_activity_at"] = now
        session["last_operation_type"] = operation_type
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session, ensure_ascii=False), encoding="utf-8")
