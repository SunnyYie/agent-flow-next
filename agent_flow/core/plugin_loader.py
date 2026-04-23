from __future__ import annotations

import importlib.util
from pathlib import Path

import click

from agent_flow.core.plugin_manifest import CommandSpec, load_plugin_manifest
from agent_flow.core.plugin_registry import PluginRegistry


def _resolve_click_command(module: object, spec: CommandSpec) -> click.Command | None:
    if spec.name:
        candidate = getattr(module, spec.name, None)
        if isinstance(candidate, click.Command):
            return candidate

    default = getattr(module, "cli", None)
    if isinstance(default, click.Command):
        return default

    for value in vars(module).values():
        if isinstance(value, click.Command):
            return value
    return None


def _load_module_from_file(module_name: str, file_path: Path) -> object:
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_enabled_plugin_commands(*, project_dir: Path, team_id: str = "") -> dict[str, click.Command]:
    commands: dict[str, click.Command] = {}
    effective = PluginRegistry.load_effective(project_dir=project_dir, team_id=team_id, enabled_only=True)

    for plugin_name, record in effective.items():
        plugin_root = Path(record.install_path)
        manifest_path = plugin_root / "manifest.yaml"
        if not manifest_path.exists():
            continue

        manifest = load_plugin_manifest(manifest_path)
        for index, command_spec in enumerate(manifest.commands):
            module_path = plugin_root / command_spec.path
            if not module_path.exists() or not module_path.is_file():
                continue

            module = _load_module_from_file(
                module_name=f"agent_flow_plugin_{plugin_name}_{index}",
                file_path=module_path,
            )
            command = _resolve_click_command(module, command_spec)
            if command is None:
                continue

            command_name = command_spec.name or command.name
            if not command_name:
                continue
            if command_name in commands:
                continue
            commands[command_name] = command

    return commands
