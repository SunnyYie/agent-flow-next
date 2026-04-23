from __future__ import annotations

import json
from pathlib import Path

import click

from agent_flow.core.skill_manager import SkillManager, SkillSpec


def _manager(scope: str) -> SkillManager:
    return SkillManager(Path.cwd(), scope=scope)


@click.group("skill")
def cli() -> None:
    """Native skill management."""


@cli.command("create")
@click.option("--name", required=True)
@click.option("--trigger", default="")
@click.option("--procedure", required=True)
@click.option("--rules", default="")
@click.option("--abstraction", default="project")
@click.option("--confidence", default=0.8, type=float)
@click.option("--scope", default="project", type=click.Choice(["project", "team", "global"]))
def create_cmd(name: str, trigger: str, procedure: str, rules: str, abstraction: str, confidence: float, scope: str) -> None:
    manager = _manager(scope)
    spec = SkillSpec(
        name=name,
        trigger=trigger,
        confidence=confidence,
        abstraction=abstraction,
    )
    try:
        path = manager.create_skill(spec, procedure=procedure, rules=rules)
    except FileExistsError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)
    click.echo(f"Created skill: {name} ({path})")


@cli.command("edit")
@click.option("--name", required=True)
@click.option("--procedure", default=None)
@click.option("--rules", default=None)
@click.option("--scope", default="project", type=click.Choice(["project", "team", "global"]))
def edit_cmd(name: str, procedure: str | None, rules: str | None, scope: str) -> None:
    manager = _manager(scope)
    try:
        manager.edit_skill(name, procedure_patch=procedure, rules_patch=rules)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)
    click.echo(f"Edited skill: {name}")


@cli.command("patch")
@click.option("--name", required=True)
@click.option("--field", multiple=True)
@click.option("--scope", default="project", type=click.Choice(["project", "team", "global"]))
def patch_cmd(name: str, field: tuple[str, ...], scope: str) -> None:
    manager = _manager(scope)
    patches: dict[str, object] = {}
    for pair in field:
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        raw = value.strip()
        if raw.lower() in {"true", "false"}:
            parsed: object = raw.lower() == "true"
        else:
            try:
                parsed = int(raw)
            except ValueError:
                try:
                    parsed = float(raw)
                except ValueError:
                    parsed = raw
        patches[key] = parsed
    try:
        manager.patch_skill(name, patches)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)
    click.echo(f"Patched skill: {name}")


@cli.command("delete")
@click.option("--name", required=True)
@click.option("--scope", default="project", type=click.Choice(["project", "team", "global"]))
def delete_cmd(name: str, scope: str) -> None:
    manager = _manager(scope)
    deleted = manager.delete_skill(name)
    if not deleted:
        click.echo(f"Skill '{name}' not found.", err=True)
        raise SystemExit(1)
    click.echo(f"Deleted skill: {name}")


@cli.command("list")
@click.option("--scope", default="project", type=click.Choice(["project", "team", "global"]))
def list_cmd(scope: str) -> None:
    manager = _manager(scope)
    skills = manager.list_skills()
    if not skills:
        click.echo("No skills found.")
        return
    for spec in skills:
        click.echo(f"{spec.name}\ttrigger={spec.trigger}\tconfidence={spec.confidence}")


@cli.command("show")
@click.option("--name", required=True)
@click.option("--scope", default="project", type=click.Choice(["project", "team", "global"]))
def show_cmd(name: str, scope: str) -> None:
    manager = _manager(scope)
    try:
        data = manager.read_skill(name)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)
    click.echo(
        json.dumps(
            {
                "spec": data["spec"].model_dump(),
                "procedure": data["procedure"],
                "rules": data["rules"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
