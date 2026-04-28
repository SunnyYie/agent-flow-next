from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.claude_settings import (
    collect_registered_plugin_commands,
    plugin_settings_path,
)
from agent_flow.core.config import project_team_id
from agent_flow.core.plugin import install_plugin, list_plugins, set_plugin_enabled, uninstall_plugin
from agent_flow.core.plugin_registry import PluginScope


_SCOPE_CHOICES = click.Choice([scope.value for scope in PluginScope])


def _resolve_team_id(scope: PluginScope, team_id: str, project_dir: Path) -> str:
    if scope != PluginScope.TEAM:
        return ""
    resolved = (team_id or project_team_id(project_dir)).strip()
    if not resolved:
        raise click.ClickException("team_id is required for team scope")
    return resolved


@click.group("plugin")
def plugin_group() -> None:
    """Manage AgentFlow plugins."""


@plugin_group.command("install")
@click.argument("name")
@click.option("--scope", "scope_name", type=_SCOPE_CHOICES, default="project", show_default=True)
@click.option("--source", default="", help="local:<path> or builtin:<name>")
@click.option("--team-id", default="", help="Team id for team scope")
def plugin_install_cmd(name: str, scope_name: str, source: str, team_id: str) -> None:
    scope = PluginScope(scope_name)
    project_dir = Path.cwd()
    resolved_team_id = _resolve_team_id(scope, team_id, project_dir)

    record = install_plugin(
        name,
        scope=scope,
        source=source or f"builtin:{name}",
        project_dir=project_dir,
        team_id=resolved_team_id,
    )
    click.echo(f"installed {record.name}@{record.version} scope={scope.value}")


@plugin_group.command("uninstall")
@click.argument("name")
@click.option("--scope", "scope_name", type=_SCOPE_CHOICES, required=True)
@click.option("--team-id", default="", help="Team id for team scope")
def plugin_uninstall_cmd(name: str, scope_name: str, team_id: str) -> None:
    scope = PluginScope(scope_name)
    project_dir = Path.cwd()
    resolved_team_id = _resolve_team_id(scope, team_id, project_dir)

    uninstall_plugin(name, scope=scope, project_dir=project_dir, team_id=resolved_team_id)
    click.echo(f"uninstalled {name} from {scope.value}")


@plugin_group.command("enable")
@click.argument("name")
@click.option("--scope", "scope_name", type=_SCOPE_CHOICES, required=True)
@click.option("--team-id", default="", help="Team id for team scope")
def plugin_enable_cmd(name: str, scope_name: str, team_id: str) -> None:
    scope = PluginScope(scope_name)
    project_dir = Path.cwd()
    resolved_team_id = _resolve_team_id(scope, team_id, project_dir)

    set_plugin_enabled(name, scope=scope, enabled=True, project_dir=project_dir, team_id=resolved_team_id)
    click.echo(f"enabled {name} in {scope.value}")


@plugin_group.command("disable")
@click.argument("name")
@click.option("--scope", "scope_name", type=_SCOPE_CHOICES, required=True)
@click.option("--team-id", default="", help="Team id for team scope")
def plugin_disable_cmd(name: str, scope_name: str, team_id: str) -> None:
    scope = PluginScope(scope_name)
    project_dir = Path.cwd()
    resolved_team_id = _resolve_team_id(scope, team_id, project_dir)

    set_plugin_enabled(name, scope=scope, enabled=False, project_dir=project_dir, team_id=resolved_team_id)
    click.echo(f"disabled {name} in {scope.value}")


@plugin_group.command("list")
@click.option("--enabled-only", is_flag=True, help="Only show enabled plugins")
def plugin_list_cmd(enabled_only: bool) -> None:
    project_dir = Path.cwd()
    team_id = project_team_id(project_dir)
    records = list_plugins(project_dir=project_dir, team_id=team_id, enabled_only=enabled_only)

    if not records:
        click.echo("no plugins")
        return

    for name, record in records.items():
        status = "enabled" if record.enabled else "disabled"
        click.echo(f"{name}\t{record.version}\t{record.scope.value}\t{status}\t{record.install_path}")


@plugin_group.command("verify")
def plugin_verify_cmd() -> None:
    """Verify project-local Claude hook registrations for effective plugins."""
    project_dir = Path.cwd()
    team_id = project_team_id(project_dir)
    records = list_plugins(project_dir=project_dir, team_id=team_id, enabled_only=True)

    expected: set[str] = set()
    for record in records.values():
        for hook in record.hook_registrations:
            expected.add(hook.command)

    actual = collect_registered_plugin_commands(project_dir)
    settings_path = plugin_settings_path(project_dir)

    missing = sorted(expected - actual)
    stale = sorted(actual - expected)

    click.echo(f"settings(primary): {settings_path}")
    click.echo(f"enabled plugins: {len(records)}")
    click.echo(f"expected hooks: {len(expected)}")
    click.echo(f"registered hooks: {len(actual)}")

    if missing:
        click.echo("\nmissing hooks:")
        for item in missing:
            click.echo(f"- {item}")
    if stale:
        click.echo("\nstale hooks:")
        for item in stale:
            click.echo(f"- {item}")

    if not missing and not stale:
        click.echo("\nplugin hooks verified: OK")
