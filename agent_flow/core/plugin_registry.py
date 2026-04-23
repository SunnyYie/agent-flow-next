from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agent_flow.core.config import team_root_base


class PluginScope(StrEnum):
    PROJECT = "project"
    TEAM = "team"
    GLOBAL = "global"


class HookRegistration(BaseModel):
    event: str
    matcher: str
    command: str


class PluginRecord(BaseModel):
    name: str
    version: str
    enabled: bool = True
    install_path: str
    source: dict[str, str] = Field(default_factory=dict)
    installed_at: str | None = None
    updated_at: str | None = None
    rollback_version: str | None = None
    previous_source: dict[str, str] | None = None
    hook_registrations: list[HookRegistration] = Field(default_factory=list)
    scope: PluginScope


class PluginRegistry:
    SCHEMA_VERSION = 1

    @staticmethod
    def registry_path(
        scope: PluginScope,
        *,
        project_dir: Path,
        team_id: str = "",
    ) -> Path:
        if scope == PluginScope.PROJECT:
            return Path(project_dir) / ".agent-flow" / "plugins" / "registry.yaml"
        if scope == PluginScope.TEAM:
            if not team_id:
                raise ValueError("team_id is required for team scope")
            return team_root_base(project_dir=project_dir) / team_id / ".agent-flow" / "plugins" / "registry.yaml"
        return Path.home() / ".agent-flow" / "plugins" / "registry.yaml"

    @classmethod
    def load_scope(
        cls,
        scope: PluginScope,
        *,
        project_dir: Path,
        team_id: str = "",
    ) -> dict[str, PluginRecord]:
        registry_file = cls.registry_path(scope, project_dir=project_dir, team_id=team_id)
        if not registry_file.exists():
            return {}

        data = yaml.safe_load(registry_file.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return {}

        plugins = data.get("plugins") or {}
        if not isinstance(plugins, dict):
            return {}

        records: dict[str, PluginRecord] = {}
        for name, payload in plugins.items():
            if not isinstance(payload, dict):
                continue
            records[name] = PluginRecord(name=name, scope=scope, **payload)
        return records

    @classmethod
    def save_scope(
        cls,
        scope: PluginScope,
        records: dict[str, PluginRecord],
        *,
        project_dir: Path,
        team_id: str = "",
    ) -> Path:
        registry_file = cls.registry_path(scope, project_dir=project_dir, team_id=team_id)
        registry_file.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {"schema_version": cls.SCHEMA_VERSION, "plugins": {}}
        for name in sorted(records):
            record = records[name]
            payload["plugins"][name] = record.model_dump(mode="json", exclude={"name", "scope"})

        registry_file.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return registry_file

    @classmethod
    def upsert_record(
        cls,
        scope: PluginScope,
        record: PluginRecord,
        *,
        project_dir: Path,
        team_id: str = "",
    ) -> Path:
        records = cls.load_scope(scope, project_dir=project_dir, team_id=team_id)
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if record.installed_at is None and record.updated_at is None:
            record.installed_at = now
        record.updated_at = now
        records[record.name] = record
        return cls.save_scope(scope, records, project_dir=project_dir, team_id=team_id)

    @classmethod
    def delete_record(
        cls,
        scope: PluginScope,
        plugin_name: str,
        *,
        project_dir: Path,
        team_id: str = "",
    ) -> Path:
        records = cls.load_scope(scope, project_dir=project_dir, team_id=team_id)
        records.pop(plugin_name, None)
        return cls.save_scope(scope, records, project_dir=project_dir, team_id=team_id)

    @classmethod
    def load_effective(
        cls,
        *,
        project_dir: Path,
        team_id: str = "",
        enabled_only: bool = False,
    ) -> dict[str, PluginRecord]:
        merged: dict[str, PluginRecord] = {}

        for scope in (PluginScope.GLOBAL, PluginScope.TEAM, PluginScope.PROJECT):
            if scope == PluginScope.TEAM and not team_id:
                continue
            scope_records = cls.load_scope(scope, project_dir=project_dir, team_id=team_id)
            for name, record in scope_records.items():
                merged[name] = record

        if enabled_only:
            merged = {name: record for name, record in merged.items() if record.enabled}

        return {name: merged[name] for name in sorted(merged)}
