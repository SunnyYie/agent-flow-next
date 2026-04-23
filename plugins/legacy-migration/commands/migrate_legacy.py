from __future__ import annotations

from pathlib import Path

import click

from agent_flow.migrations.legacy import migrate_legacy_assets


@click.command("migrate-legacy")
@click.option("--legacy-project", required=True)
@click.option("--global-source", required=True)
@click.option("--team-id", required=True)
@click.option("--include-project-knowledge", is_flag=True, help="Also migrate legacy project .agent-flow/.dev-workflow knowledge.")
def cli(legacy_project: str, global_source: str, team_id: str, include_project_knowledge: bool) -> None:
    report = migrate_legacy_assets(
        legacy_project_dir=Path(legacy_project),
        global_source_dir=Path(global_source),
        project_dir=Path.cwd(),
        team_id=team_id,
        include_project_knowledge=include_project_knowledge,
    )
    click.echo(report)
