from __future__ import annotations

from pathlib import Path

import click

from agent_flow.cli.plugin import plugin_group
from agent_flow.core.config import (
    TEAM_HOOKS_PROFILE_FULL,
    TEAM_HOOKS_PROFILE_MINIMAL,
    init_global,
    init_project,
    init_team,
    project_team_id,
)
from agent_flow.core.plugin import ensure_default_builtin_plugins
from agent_flow.core.plugin_loader import load_enabled_plugin_commands
from agent_flow.core.plugin_selection import select_plugins_interactive
from agent_flow.core.plugin_registry import PluginScope
from agent_flow.core.request_context import parse_request_prompt


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
@click.option("--plugins", default="", help="Comma-separated builtin plugin names")
@click.option(
    "--hooks-profile",
    type=click.Choice([TEAM_HOOKS_PROFILE_MINIMAL, TEAM_HOOKS_PROFILE_FULL]),
    default=TEAM_HOOKS_PROFILE_MINIMAL,
    show_default=True,
    help="Team hook template profile for --team init",
)
def init_cmd(is_global: bool, is_team: bool, is_project: bool, team_id: str, plugins: str, hooks_profile: str) -> None:
    try:
        selected_plugins = (
            select_plugins_interactive(plugin_names=[name.strip() for name in plugins.split(",") if name.strip()])
            if plugins.strip()
            else select_plugins_interactive()
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if is_global:
        project = Path.cwd()
        click.echo(str(init_global(project_dir=project)))
        ensure_default_builtin_plugins(
            scope=PluginScope.GLOBAL,
            project_dir=project,
            selected_plugins=selected_plugins,
        )
        return
    if is_team:
        if not team_id:
            raise click.ClickException("--team requires --team-id")
        project = Path.cwd()
        click.echo(str(init_team(team_id, project_dir=project, hooks_profile=hooks_profile)))
        ensure_default_builtin_plugins(
            scope=PluginScope.TEAM,
            project_dir=project,
            team_id=team_id,
            selected_plugins=selected_plugins,
        )
        return
    # default project
    project = Path.cwd()
    click.echo(str(init_project(project)))
    ensure_default_builtin_plugins(
        scope=PluginScope.PROJECT,
        project_dir=project,
        selected_plugins=selected_plugins,
    )


@cli.command("request-parse")
@click.option("--prompt", required=True, help="Raw user prompt to structure")
def request_parse_cmd(prompt: str) -> None:
    """Parse a natural-language execution prompt into structured request JSON."""
    context = parse_request_prompt(prompt)
    click.echo(context.model_dump_json(indent=2))


cli.add_command(plugin_group)
