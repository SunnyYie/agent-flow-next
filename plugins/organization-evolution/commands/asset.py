from __future__ import annotations

import json
from pathlib import Path

import click

from agent_flow.core.config import layer_root, project_team_id
from agent_flow.resources.resolver import ResourceResolver


def _resolver_for_project(project: Path, team_id_override: str = "") -> ResourceResolver:
    team_id = team_id_override or project_team_id(project)
    return ResourceResolver(
        global_root=layer_root("global", project_dir=project),
        team_root=layer_root("team", team_id=team_id, project_dir=project) if team_id else None,
        project_root=layer_root("project", project_dir=project),
    )


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


@click.group("asset")
def cli() -> None:
    pass


@cli.command("resolve")
def resolve_cmd() -> None:
    project = Path.cwd()
    rr = _resolver_for_project(project)
    resolved = rr.resolve_all()
    for kind, values in resolved.items():
        click.echo(f"{kind}: {len(values)}")


@cli.command("list")
@click.option("--kind", "kind_filter", type=click.Choice(["skills", "wiki", "references", "tools", "hooks", "souls", "all"]), default="all")
@click.option("--layer", "layer_filter", type=click.Choice(["global", "team", "project", "all"]), default="all")
@click.option("--team-id", default="", help="Override team id instead of project binding")
def list_cmd(kind_filter: str, layer_filter: str, team_id: str) -> None:
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


@cli.command("show")
@click.option("--kind", "kind_name", required=True, type=click.Choice(["skills", "wiki", "references", "tools", "hooks", "souls"]))
@click.option("--name", "asset_name", required=True, help="Asset key/name")
@click.option("--team-id", default="", help="Override team id instead of project binding")
def show_cmd(kind_name: str, asset_name: str, team_id: str) -> None:
    project = Path.cwd()
    resolved = _resolver_for_project(project, team_id_override=team_id).resolve_all()
    entry = resolved[kind_name].get(asset_name)
    if not entry:
        raise click.ClickException(f"asset not found: kind={kind_name}, name={asset_name}")

    click.echo(f"kind: {kind_name}")
    click.echo(f"name: {asset_name}")
    click.echo(f"layer: {entry.layer}")
    click.echo(f"path: {entry.path}")


@cli.command("create")
@click.option("--kind", "kind_name", required=True, type=click.Choice(["skills", "wiki", "references", "tools", "hooks", "souls"]))
@click.option("--name", "asset_name", required=True, help="Asset key/name")
@click.option("--layer", "layer_name", required=True, type=click.Choice(["global", "team", "project"]))
@click.option("--team-id", default="", help="Required for team layer")
@click.option("--force", is_flag=True, help="Overwrite when target exists")
def create_cmd(kind_name: str, asset_name: str, layer_name: str, team_id: str, force: bool) -> None:
    project = Path.cwd()
    target = _asset_target_path(project, kind_name, layer_name, asset_name, team_id)
    if target.exists() and not force:
        raise click.ClickException(f"target already exists: {target} (use --force to overwrite)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_asset_template(kind_name, asset_name), encoding="utf-8")
    click.echo(str(target))


@cli.command("lint")
@click.option("--team-id", default="", help="Override team id instead of project binding")
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
def lint_cmd(team_id: str, json_output: bool) -> None:
    project = Path.cwd()
    resolved = _resolver_for_project(project, team_id_override=team_id).resolve_all()
    issues: list[str] = []
    warnings: list[str] = []

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
