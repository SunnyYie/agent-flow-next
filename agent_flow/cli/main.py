from __future__ import annotations

from pathlib import Path

import click

from agent_flow.cli.plugin import plugin_group
from agent_flow.core.config import init_global, init_project, init_team, project_team_id
from agent_flow.core.plugin import ensure_default_builtin_plugins
from agent_flow.core.plugin_loader import load_enabled_plugin_commands
from agent_flow.core.plugin_registry import PluginScope


class PluginAwareGroup(click.Group):
    def _plugin_commands(self) -> dict[str, click.Command]:
        project = Path.cwd()
        team_id = project_team_id(project)
        return load_enabled_plugin_commands(project_dir=project, team_id=team_id)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        command = super().get_command(ctx, cmd_name)
        if command is not None:
            return command
        return self._plugin_commands().get(cmd_name)

    def list_commands(self, ctx: click.Context) -> list[str]:
        static_names = super().list_commands(ctx)
        plugin_names = list(self._plugin_commands().keys())
        return sorted(set(static_names + plugin_names))


@click.group(cls=PluginAwareGroup)
@click.version_option(version="0.1.0")
def cli() -> None:
    """AgentFlow Next CLI."""


@cli.command("init")
@click.option("--global", "is_global", is_flag=True)
@click.option("--team", "is_team", is_flag=True)
@click.option("--project", "is_project", is_flag=True)
@click.option("--team-id", default="")
def init_cmd(is_global: bool, is_team: bool, is_project: bool, team_id: str) -> None:
    if is_global:
        project = Path.cwd()
        click.echo(str(init_global(project_dir=project)))
        ensure_default_builtin_plugins(scope=PluginScope.GLOBAL, project_dir=project)
        return
    if is_team:
        if not team_id:
            raise click.ClickException("--team requires --team-id")
        project = Path.cwd()
        click.echo(str(init_team(team_id, project_dir=project)))
        ensure_default_builtin_plugins(scope=PluginScope.TEAM, project_dir=project, team_id=team_id)
        return
    # default project
    project = Path.cwd()
    click.echo(str(init_project(project)))
    ensure_default_builtin_plugins(scope=PluginScope.PROJECT, project_dir=project)


cli.add_command(plugin_group)
