from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.config import TEAM_HOOKS_PROFILE_FULL, TEAM_HOOKS_PROFILE_MINIMAL, init_team_flow


@click.command("init-team-flow")
@click.option("--team-id", required=True)
@click.option("--name", default="")
@click.option(
    "--hooks-profile",
    type=click.Choice([TEAM_HOOKS_PROFILE_MINIMAL, TEAM_HOOKS_PROFILE_FULL]),
    default=TEAM_HOOKS_PROFILE_MINIMAL,
    show_default=True,
    help="Team hook template profile",
)
def cli(team_id: str, name: str, hooks_profile: str) -> None:
    click.echo(str(init_team_flow(team_id=team_id, name=name, project_dir=Path.cwd(), hooks_profile=hooks_profile)))
