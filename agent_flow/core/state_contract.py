"""Shared state-contract helpers for AgentFlow runtime, CLI, and hooks.

This module defines the canonical state directory and document/schema
compatibility rules used across the project.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


CANONICAL_PLAN_CORE_HEADERS = [
    "# 任务:",
    "## 复杂度",
    "## RPI 阶段规划",
    "## 实施计划",
    "## 变更点",
    "## 验收标准",
]
CANONICAL_PLAN_OPTIONAL_HEADERS = [
    "## 实现期待确认事项",
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

DEFAULT_FLOW_CONTEXT_SCHEMA_VERSION = 2
DEFAULT_COMPLEXITY_LEVEL = "medium"
REQUIRED_MARKER_FIELDS = ("timestamp", "task", "confirmed_by", "summary")
DEFAULT_MARKER_FIELD_ORDER = ("phase", "status", "timestamp", "task", "confirmed_by", "summary")
STRUCTURED_MARKER_FILES = frozenset({
    ".requirement-clarified",
    ".design-confirmed",
    ".mcp-tool-factory-requested",
    ".user-acceptance-done",
})


@dataclass(frozen=True)
class StatePaths:
    project_root: Path
    canonical_dir: Path
    legacy_dir: Path

    def candidates(self, filename: str) -> list[Path]:
        return [
            self.canonical_dir / filename,
            self.legacy_dir / filename,
        ]

    def read_path(self, filename: str) -> Path:
        for path in self.candidates(filename):
            if path.is_file():
                return path
        return self.write_path(filename)

    def write_path(self, filename: str) -> Path:
        return self.canonical_dir / filename


def find_project_root(start: Path | str | None = None) -> Path | None:
    """Find the nearest project root containing .agent-flow or .dev-workflow."""
    current = Path(start or ".").resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".agent-flow").exists() or (candidate / ".dev-workflow").exists():
            return candidate
    return None


def get_state_paths(project_root: Path | str) -> StatePaths:
    root = Path(project_root).resolve()
    return StatePaths(
        project_root=root,
        canonical_dir=root / ".agent-flow" / "state",
        legacy_dir=root / ".dev-workflow" / "state",
    )


def detect_plan_format(content: str) -> str:
    """Detect whether plan content is canonical, legacy-compatible, or absent."""
    normalized = content or ""
    if all(header in normalized for header in CANONICAL_PLAN_CORE_HEADERS):
        return "canonical"
    if any(marker in normalized for marker in LEGACY_PLAN_MARKERS):
        return "legacy"
    return "none"


def has_implementation_plan(content: str) -> bool:
    return detect_plan_format(content) in {"canonical", "legacy"}


def get_complexity_level(project_root: Path | str) -> str:
    state_paths = get_state_paths(project_root)
    complexity_file = state_paths.read_path(".complexity-level")
    if not complexity_file.is_file():
        return DEFAULT_COMPLEXITY_LEVEL

    try:
        for line in complexity_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("level="):
                level = stripped.split("=", 1)[1].strip().lower()
                if level in {"simple", "medium", "complex"}:
                    return level
    except OSError:
        pass
    return DEFAULT_COMPLEXITY_LEVEL


def load_marker_entries(path: Path | str) -> list[dict[str, str]]:
    """Load structured key-value marker entries separated by blank lines."""
    marker_path = Path(path)
    if not marker_path.is_file():
        return []

    try:
        raw = marker_path.read_text(encoding="utf-8").strip()
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


def marker_has_required_fields(entry: dict[str, str]) -> bool:
    return all(entry.get(field, "").strip() for field in REQUIRED_MARKER_FIELDS)


def is_structured_marker_file(path: Path | str) -> bool:
    return Path(path).name in STRUCTURED_MARKER_FILES


def serialize_marker_entry(entry: dict[str, str]) -> str:
    """Serialize a structured marker entry into stable key-value lines."""
    ordered_keys: list[str] = []
    for key in DEFAULT_MARKER_FIELD_ORDER:
        if key in entry and str(entry.get(key, "")).strip():
            ordered_keys.append(key)

    extra_keys = sorted(
        key for key, value in entry.items()
        if key not in DEFAULT_MARKER_FIELD_ORDER and str(value).strip()
    )
    ordered_keys.extend(extra_keys)
    return "\n".join(f"{key}={entry[key]}" for key in ordered_keys)


def normalize_flow_context_data(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize legacy and canonical flow-context payloads to canonical schema."""
    data = raw or {}
    workflow = data.get("workflow", {}) if isinstance(data.get("workflow"), dict) else {}

    normalized: dict[str, Any] = {
        "schema_version": int(data.get("schema_version") or DEFAULT_FLOW_CONTEXT_SCHEMA_VERSION),
        "workflow_id": data.get("workflow_id") or workflow.get("id") or "",
        "phase": data.get("phase") or workflow.get("phase") or "IDLE",
        "started_at": data.get("started_at") or workflow.get("started") or workflow.get("started_at") or "",
        "context_budget": _normalize_context_budget(data.get("context_budget")),
        "tasks": _normalize_tasks(data.get("tasks")),
        "agents": _normalize_agents(data.get("agents")),
        "recovery": _normalize_recovery(data.get("recovery")),
    }
    return normalized


def default_flow_context_data(workflow_id: str = "", phase: str = "IDLE") -> dict[str, Any]:
    """Return canonical default flow-context data."""
    return normalize_flow_context_data(
        {
            "schema_version": DEFAULT_FLOW_CONTEXT_SCHEMA_VERSION,
            "workflow_id": workflow_id,
            "phase": phase,
            "started_at": "",
            "context_budget": {},
            "tasks": [],
            "agents": [],
            "recovery": {},
        }
    )


def _normalize_context_budget(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "used": int(source.get("used", 0) or 0),
        "max": int(source.get("max", 200000) or 200000),
        "status": source.get("status", "healthy") or "healthy",
        "files_read": int(source.get("files_read", 0) or 0),
        "last_update": source.get("last_update", "") or "",
    }


def _normalize_tasks(raw: Any) -> list[dict[str, Any]]:
    items = raw if isinstance(raw, list) else []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "id": int(item.get("id", 0) or 0),
                "title": item.get("title", "") or "",
                "status": item.get("status", "pending") or "pending",
                "agent_name": item.get("agent_name") or item.get("agent") or "",
                "summary": item.get("summary", "") or "",
                "artifact_path": item.get("artifact_path") or item.get("artifact") or "",
                "depends_on": [int(dep) for dep in (item.get("depends_on") or [])],
                "verified": bool(item.get("verified", False)),
                "verification_path": item.get("verification_path", "") or "",
                "assigned_files": [str(f) for f in (item.get("assigned_files") or [])],
            }
        )
    return normalized


def _normalize_agents(raw: Any) -> list[dict[str, Any]]:
    items = raw if isinstance(raw, list) else []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "name": item.get("name", "") or "",
                "role": item.get("role", "executor") or "executor",
                "status": item.get("status", "running") or "running",
                "task_id": int(item.get("task_id") or item.get("task") or 0),
                "started_at": item.get("started_at", "") or "",
                "completed_at": item.get("completed_at", "") or "",
            }
        )
    return normalized


def _normalize_recovery(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    interrupted = source.get("interrupted_task", 0)
    if interrupted in (None, ""):
        interrupted = 0
    return {
        "last_checkpoint": source.get("last_checkpoint", "") or "",
        "interrupted_task": int(interrupted or 0),
        "partial_artifacts": [str(path) for path in (source.get("partial_artifacts") or [])],
    }
