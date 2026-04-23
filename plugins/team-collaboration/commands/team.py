from __future__ import annotations

from pathlib import Path

import click
import yaml

from agent_flow.core.config import layer_root, project_team_id, team_root_base
from agent_flow.resources.resolver import ResourceResolver


def _resolve_team_root(project: Path, team_id: str) -> Path:
    resolved_team_id = team_id or project_team_id(project)
    if not resolved_team_id:
        raise click.ClickException("no team id provided and project has no team binding")
    return layer_root("team", team_id=resolved_team_id, project_dir=project)


@click.group("team")
def cli() -> None:
    pass


@cli.command("list")
def list_cmd() -> None:
    base = team_root_base(project_dir=Path.cwd())
    if not base.exists():
        click.echo("no teams found")
        return
    rows: list[str] = []
    for team_dir in sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        team_yaml = team_dir / "team.yaml"
        if not team_yaml.exists():
            continue
        data = yaml.safe_load(team_yaml.read_text(encoding="utf-8")) or {}
        label = data.get("name") or team_dir.name
        rows.append(f"{team_dir.name}\t{label}")
    if not rows:
        click.echo("no teams found")
        return
    for row in rows:
        click.echo(row)


@cli.command("info")
@click.option("--team-id", default="", help="Team id; default uses project binding")
def info_cmd(team_id: str) -> None:
    project = Path.cwd()
    root = _resolve_team_root(project, team_id)
    team_yaml = root / "team.yaml"
    if not team_yaml.exists():
        raise click.ClickException(f"missing team.yaml: {team_yaml}")
    data = yaml.safe_load(team_yaml.read_text(encoding="utf-8")) or {}
    rr = ResourceResolver(global_root=layer_root("global", project_dir=project), team_root=root, project_root=None)
    resolved = rr.resolve_all()
    click.echo(f"team_id: {data.get('team_id', root.name)}")
    click.echo(f"name: {data.get('name', '')}")
    click.echo(f"root: {root}")
    click.echo(f"schema_version: {data.get('schema_version', '')}")
    click.echo("asset_counts:")
    click.echo(f"  skills: {len(resolved['skills'])}")
    click.echo(f"  wiki: {len(resolved['wiki'])}")
    click.echo(f"  references: {len(resolved['references'])}")
    click.echo(f"  tools: {len(resolved['tools'])}")
    click.echo(f"  hooks: {len(resolved['hooks'])}")
    click.echo(f"  souls: {len(resolved['souls'])}")
