from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.config import bind_project_team


@click.command("bind-team")
@click.argument("team_id")
def cli(team_id: str) -> None:
    bind_project_team(Path.cwd(), team_id)
    click.echo(f"bound to team {team_id}")
