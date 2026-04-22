from __future__ import annotations

import json
from pathlib import Path

import click
import yaml

from agent_flow.core.config import (
    bind_project_team,
    init_global,
    init_project,
    init_team,
    init_team_flow,
    layer_root,
    team_root_base,
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


@cli.command("init-team-flow")
@click.option("--team-id", required=True)
@click.option("--name", default="")
def init_team_flow_cmd(team_id: str, name: str) -> None:
    click.echo(str(init_team_flow(team_id=team_id, name=name, project_dir=Path.cwd())))


@cli.command("bind-team")
@click.argument("team_id")
def bind_team_cmd(team_id: str) -> None:
    bind_project_team(Path.cwd(), team_id)
    click.echo(f"bound to team {team_id}")


@cli.group("asset")
def asset_group() -> None:
    pass


def _resolver_for_project(project: Path, team_id_override: str = "") -> ResourceResolver:
    team_id = team_id_override or project_team_id(project)
    return ResourceResolver(
        global_root=layer_root("global", project_dir=project),
        team_root=layer_root("team", team_id=team_id, project_dir=project) if team_id else None,
        project_root=layer_root("project", project_dir=project),
    )


@asset_group.command("resolve")
def asset_resolve_cmd() -> None:
    project = Path.cwd()
    rr = _resolver_for_project(project)
    resolved = rr.resolve_all()
    for kind, values in resolved.items():
        click.echo(f"{kind}: {len(values)}")


@asset_group.command("list")
@click.option("--kind", "kind_filter", type=click.Choice(["skills", "wiki", "references", "tools", "hooks", "souls", "all"]), default="all")
@click.option("--layer", "layer_filter", type=click.Choice(["global", "team", "project", "all"]), default="all")
@click.option("--team-id", default="", help="Override team id instead of project binding")
def asset_list_cmd(kind_filter: str, layer_filter: str, team_id: str) -> None:
    project = Path.cwd()
    resolved = _resolver_for_project(project, team_id_override=team_id).resolve_all()
    kinds = [kind_filter] if kind_filter != "all" else ["skills", "wiki", "references", "tools", "hooks", "souls"]

    rows: list[tuple[str, str, str, str]] = []
    for kind in kinds:
        for key, entry in sorted(resolved[kind].items(), key=lambda item: item[0]):
            if layer_filter != "all" and entry.layer != layer_filter:
                continue
            rows.append((kind, key, entry.layer, str(entry.path)))

    if not rows:
        click.echo("no assets matched")
        return

    for kind, key, layer, path in rows:
        click.echo(f"{kind}\t{key}\t{layer}\t{path}")


@asset_group.command("show")
@click.option("--kind", "kind_name", required=True, type=click.Choice(["skills", "wiki", "references", "tools", "hooks", "souls"]))
@click.option("--name", "asset_name", required=True, help="Asset key/name")
@click.option("--team-id", default="", help="Override team id instead of project binding")
def asset_show_cmd(kind_name: str, asset_name: str, team_id: str) -> None:
    project = Path.cwd()
    resolved = _resolver_for_project(project, team_id_override=team_id).resolve_all()
    entry = resolved[kind_name].get(asset_name)
    if not entry:
        raise click.ClickException(f"asset not found: kind={kind_name}, name={asset_name}")

    click.echo(f"kind: {kind_name}")
    click.echo(f"name: {asset_name}")
    click.echo(f"layer: {entry.layer}")
    click.echo(f"path: {entry.path}")


def _asset_target_path(project: Path, kind_name: str, layer_name: str, name: str, team_id: str) -> Path:
    if layer_name == "project":
        root = layer_root("project", project_dir=project)
    elif layer_name == "global":
        root = layer_root("global", project_dir=project)
    else:
        if not team_id:
            raise click.ClickException("--team-id is required when --layer team")
        root = layer_root("team", team_id=team_id, project_dir=project)

    if kind_name == "skills":
        return root / "skills" / name / "SKILL.md"
    if kind_name == "wiki":
        return root / "wiki" / f"{name}.md"
    if kind_name == "references":
        return root / "references" / f"{name}.md"
    if kind_name == "tools":
        return root / "tools" / f"{name}.yaml"
    if kind_name == "hooks":
        return root / "hooks" / f"{name}.py"
    if kind_name == "souls":
        return root / "souls" / f"{name}.md"
    raise click.ClickException(f"unsupported kind: {kind_name}")


def _asset_template(kind_name: str, name: str) -> str:
    if kind_name == "skills":
        return f"# {name}\n\n## Trigger\n\n## Procedure\n\n## Rules\n"
    if kind_name in {"wiki", "references", "souls"}:
        return f"# {name}\n"
    if kind_name == "tools":
        return "version: 1\n"
    if kind_name == "hooks":
        return "from __future__ import annotations\n\n\ndef handle(event: dict) -> None:\n    return None\n"
    return ""


@asset_group.command("create")
@click.option("--kind", "kind_name", required=True, type=click.Choice(["skills", "wiki", "references", "tools", "hooks", "souls"]))
@click.option("--name", "asset_name", required=True, help="Asset key/name")
@click.option("--layer", "layer_name", required=True, type=click.Choice(["global", "team", "project"]))
@click.option("--team-id", default="", help="Required for team layer")
@click.option("--force", is_flag=True, help="Overwrite when target exists")
def asset_create_cmd(kind_name: str, asset_name: str, layer_name: str, team_id: str, force: bool) -> None:
    project = Path.cwd()
    target = _asset_target_path(project, kind_name, layer_name, asset_name, team_id)
    if target.exists() and not force:
        raise click.ClickException(f"target already exists: {target} (use --force to overwrite)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_asset_template(kind_name, asset_name), encoding="utf-8")
    click.echo(str(target))


@asset_group.command("lint")
@click.option("--team-id", default="", help="Override team id instead of project binding")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def asset_lint_cmd(team_id: str, json_output: bool) -> None:
    project = Path.cwd()
    resolved = _resolver_for_project(project, team_id_override=team_id).resolve_all()
    issues: list[str] = []
    warnings: list[str] = []

    # Basic integrity checks.
    if not resolved["souls"]:
        issues.append("no souls resolved across layers")

    explicit_team_id = team_id or project_team_id(project)
    if explicit_team_id:
        team_root = layer_root("team", team_id=explicit_team_id, project_dir=project)
        if not team_root.exists():
            issues.append(f"team layer not found: {team_root}")
        for index_name in ("skills/Index.md", "wiki/Index.md"):
            if not (team_root / index_name).exists():
                warnings.append(f"missing team index: {team_root / index_name}")

    for kind in ("skills", "wiki", "tools", "hooks", "souls"):
        by_key: dict[str, set[str]] = {}
        for key, entry in resolved[kind].items():
            by_key.setdefault(key, set()).add(entry.layer)
        for key, layers in sorted(by_key.items()):
            if len(layers) > 1:
                warnings.append(f"{kind} shadow chain detected for '{key}': {','.join(sorted(layers))}")

    payload = {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "counts": {k: len(v) for k, v in resolved.items()},
    }
    if json_output:
        click.echo(json.dumps(payload, ensure_ascii=False))
    else:
        click.echo(payload)
    if issues:
        raise SystemExit(1)


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


@cli.group("team")
def team_group() -> None:
    pass


def _resolve_team_root(project: Path, team_id: str) -> Path:
    resolved_team_id = team_id or project_team_id(project)
    if not resolved_team_id:
        raise click.ClickException("no team id provided and project has no team binding")
    return layer_root("team", team_id=resolved_team_id, project_dir=project)


@team_group.command("list")
def team_list_cmd() -> None:
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


@team_group.command("info")
@click.option("--team-id", default="", help="Team id; default uses project binding")
def team_info_cmd(team_id: str) -> None:
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


@cli.command("doctor")
@click.option("--json", "json_output", is_flag=True, help="Output diagnostics as JSON")
def doctor_cmd(json_output: bool) -> None:
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
