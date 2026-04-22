from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.config import (
    bind_project_team,
    init_global,
    init_project,
    init_team,
    layer_root,
)
from agent_flow.core.doctor import run_doctor
from agent_flow.core.config import project_team_id
from agent_flow.resources.resolver import ResourceResolver
from agent_flow.governance.promotions import PromotionManager
from agent_flow.migrations.legacy import migrate_legacy_assets


@click.group()
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
        click.echo(str(init_global(project_dir=Path.cwd())))
        return
    if is_team:
        if not team_id:
            raise click.ClickException("--team requires --team-id")
        click.echo(str(init_team(team_id, project_dir=Path.cwd())))
        return
    # default project
    click.echo(str(init_project(Path.cwd())))


@cli.command("bind-team")
@click.argument("team_id")
def bind_team_cmd(team_id: str) -> None:
    bind_project_team(Path.cwd(), team_id)
    click.echo(f"bound to team {team_id}")


@cli.group("asset")
def asset_group() -> None:
    pass


@asset_group.command("resolve")
def asset_resolve_cmd() -> None:
    project = Path.cwd()
    team_id = project_team_id(project)
    rr = ResourceResolver(
        global_root=layer_root("global", project_dir=project),
        team_root=layer_root("team", team_id=team_id, project_dir=project) if team_id else None,
        project_root=layer_root("project", project_dir=project),
    )
    resolved = rr.resolve_all()
    for kind, values in resolved.items():
        click.echo(f"{kind}: {len(values)}")


@cli.group("promote")
def promote_group() -> None:
    pass


@promote_group.command("submit")
@click.option("--kind", required=True)
@click.option("--name", required=True)
@click.option("--from-layer", required=True)
@click.option("--to-layer", required=True)
@click.option("--team-id", required=True)
@click.option("--source-path", required=True)
def promote_submit(kind: str, name: str, from_layer: str, to_layer: str, team_id: str, source_path: str) -> None:
    mgr = PromotionManager(base_dir=layer_root("project", project_dir=Path.cwd()))
    pid = mgr.submit(kind=kind, name=name, from_layer=from_layer, to_layer=to_layer, team_id=team_id, source_path=source_path)
    click.echo(pid)


@promote_group.command("review")
@click.argument("proposal_id")
@click.option("--reviewer", required=True)
@click.option("--role", required=True)
@click.option("--decision", required=True)
@click.option("--summary", default="")
def promote_review(proposal_id: str, reviewer: str, role: str, decision: str, summary: str) -> None:
    mgr = PromotionManager(base_dir=layer_root("project", project_dir=Path.cwd()))
    mgr.add_human_review(proposal_id, reviewer=reviewer, role=role, decision=decision, summary=summary)
    click.echo("ok")


@promote_group.command("ai-review")
@click.argument("proposal_id")
@click.option("--profile", required=True)
@click.option("--decision", required=True)
@click.option("--summary", required=True)
def promote_ai_review(proposal_id: str, profile: str, decision: str, summary: str) -> None:
    mgr = PromotionManager(base_dir=layer_root("project", project_dir=Path.cwd()))
    mgr.add_ai_review(proposal_id, profile=profile, decision=decision, summary=summary)
    click.echo("ok")


@promote_group.command("status")
@click.argument("proposal_id")
def promote_status(proposal_id: str) -> None:
    mgr = PromotionManager(base_dir=layer_root("project", project_dir=Path.cwd()))
    click.echo(mgr.status(proposal_id))


@promote_group.command("finalize")
@click.argument("proposal_id")
def promote_finalize(proposal_id: str) -> None:
    mgr = PromotionManager(base_dir=layer_root("project", project_dir=Path.cwd()))
    click.echo(mgr.finalize(proposal_id))


@cli.command("doctor")
def doctor_cmd() -> None:
    project = Path.cwd()
    team_id = project_team_id(project)
    report = run_doctor(
        project_dir=project,
        global_root=layer_root("global", project_dir=project),
        team_root=layer_root("team", team_id=team_id, project_dir=project) if team_id else None,
    )
    click.echo(report)


@cli.command("migrate-legacy")
@click.option("--legacy-project", required=True)
@click.option("--global-source", required=True)
@click.option("--team-id", required=True)
@click.option("--include-project-knowledge", is_flag=True, help="Also migrate legacy project .agent-flow/.dev-workflow knowledge.")
def migrate_legacy_cmd(legacy_project: str, global_source: str, team_id: str, include_project_knowledge: bool) -> None:
    report = migrate_legacy_assets(
        legacy_project_dir=Path(legacy_project),
        global_source_dir=Path(global_source),
        project_dir=Path.cwd(),
        team_id=team_id,
        include_project_knowledge=include_project_knowledge,
    )
    click.echo(report)
