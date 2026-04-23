#!/usr/bin/env python3
"""Shared AgentFlow hook helpers for state-contract compatibility."""

from __future__ import annotations

import os
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
        if (candidate / ".agent-flow").exists() or (candidate / ".dev-workflow").exists():
            return candidate
    return None


def get_state_dirs(project_root: Path) -> tuple[Path, Path]:
    return (
        project_root / ".agent-flow" / "state",
        project_root / ".dev-workflow" / "state",
    )


def read_state_path(project_root: Path, filename: str) -> Path:
    canonical, legacy = get_state_dirs(project_root)
    for path in [canonical / filename, legacy / filename]:
        if path.is_file():
            return path
    return canonical / filename


def write_state_path(project_root: Path, filename: str) -> Path:
    canonical, _ = get_state_dirs(project_root)
    return canonical / filename


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
