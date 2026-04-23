from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class PluginSource(BaseModel):
    type: Literal["builtin", "local", "git", "pip"]
    location: str = ""
    ref: str = ""


class CommandSpec(BaseModel):
    path: str
    name: str | None = None
    group: bool = False


class HookSpec(BaseModel):
    path: str
    event: str
    matcher: str = ""


class PluginManifest(BaseModel):
    api_version: int
    name: str
    version: str
    description: str = ""
    namespace: str
    commands: list[CommandSpec] = Field(default_factory=list)
    hooks: list[HookSpec] = Field(default_factory=list)
    source: PluginSource | None = None
    requires: dict[str, Any] = Field(default_factory=dict)
    exclusive: dict[str, list[str]] = Field(default_factory=dict)
    settings: dict[str, Any] = Field(default_factory=dict)


def load_plugin_manifest(manifest_path: Path) -> PluginManifest:
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"invalid manifest format: {manifest_path}")
    return PluginManifest(**raw)
