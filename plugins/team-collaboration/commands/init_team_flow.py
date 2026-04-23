from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.config import init_team_flow


@click.command("init-team-flow")
@click.option("--team-id", required=True)
@click.option("--name", default="")
def cli(team_id: str, name: str) -> None:
    click.echo(str(init_team_flow(team_id=team_id, name=name, project_dir=Path.cwd())))
