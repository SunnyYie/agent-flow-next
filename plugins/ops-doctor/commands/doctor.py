from __future__ import annotations

import json
from pathlib import Path

import click

from agent_flow.core.config import layer_root, project_team_id
from agent_flow.core.doctor import run_doctor


@click.command("doctor")
@click.option("--json", "json_output", is_flag=True, help="Output diagnostics as JSON")
def cli(json_output: bool) -> None:
    project = Path.cwd()
    team_id = project_team_id(project)
    report = run_doctor(
        project_dir=project,
        global_root=layer_root("global", project_dir=project),
        team_root=layer_root("team", team_id=team_id, project_dir=project) if team_id else None,
    )
    if json_output:
        click.echo(json.dumps(report, ensure_ascii=False))
    else:
        click.echo(report)
