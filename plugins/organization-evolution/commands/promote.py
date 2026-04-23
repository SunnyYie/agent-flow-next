from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.config import layer_root, project_team_id
from agent_flow.governance.promotions import PromotionManager


def _promotion_mgr_for_project(project: Path, team_id_override: str = "") -> PromotionManager:
    team_id = team_id_override or project_team_id(project)
    if not team_id:
        raise click.ClickException("no team id provided and project has no team binding")
    return PromotionManager(
        project_root=layer_root("project", project_dir=project),
        team_root=layer_root("team", team_id=team_id, project_dir=project),
        global_root=layer_root("global", project_dir=project),
    )


@click.group("promote")
def cli() -> None:
    pass


@cli.command("submit")
@click.option("--kind", required=True)
@click.option("--name", required=True)
@click.option("--from-layer", required=True)
@click.option("--to-layer", required=True)
@click.option("--team-id", required=True)
@click.option("--source-path", required=True)
def submit_cmd(kind: str, name: str, from_layer: str, to_layer: str, team_id: str, source_path: str) -> None:
    mgr = _promotion_mgr_for_project(project=Path.cwd(), team_id_override=team_id)
    pid = mgr.submit(kind=kind, name=name, from_layer=from_layer, to_layer=to_layer, team_id=team_id, source_path=source_path)
    click.echo(pid)


@cli.command("review")
@click.argument("proposal_id")
@click.option("--team-id", default="", help="Override team id instead of project binding")
@click.option("--reviewer", required=True)
@click.option("--role", required=True)
@click.option("--decision", required=True)
@click.option("--summary", default="")
def review_cmd(proposal_id: str, team_id: str, reviewer: str, role: str, decision: str, summary: str) -> None:
    mgr = _promotion_mgr_for_project(project=Path.cwd(), team_id_override=team_id)
    mgr.add_human_review(proposal_id, reviewer=reviewer, role=role, decision=decision, summary=summary)
    click.echo("ok")


@cli.command("ai-review")
@click.argument("proposal_id")
@click.option("--team-id", default="", help="Override team id instead of project binding")
@click.option("--profile", required=True)
@click.option("--decision", required=True)
@click.option("--summary", required=True)
def ai_review_cmd(proposal_id: str, team_id: str, profile: str, decision: str, summary: str) -> None:
    mgr = _promotion_mgr_for_project(project=Path.cwd(), team_id_override=team_id)
    mgr.add_ai_review(proposal_id, profile=profile, decision=decision, summary=summary)
    click.echo("ok")


@cli.command("status")
@click.argument("proposal_id")
@click.option("--team-id", default="", help="Override team id instead of project binding")
def status_cmd(proposal_id: str, team_id: str) -> None:
    mgr = _promotion_mgr_for_project(project=Path.cwd(), team_id_override=team_id)
    click.echo(mgr.status(proposal_id))


@cli.command("finalize")
@click.argument("proposal_id")
@click.option("--team-id", default="", help="Override team id instead of project binding")
def finalize_cmd(proposal_id: str, team_id: str) -> None:
    mgr = _promotion_mgr_for_project(project=Path.cwd(), team_id_override=team_id)
    click.echo(mgr.finalize(proposal_id))
