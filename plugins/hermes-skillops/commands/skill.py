from __future__ import annotations

from pathlib import Path

import click


def _root(scope: str) -> Path:
    if scope == "global":
        return Path.home() / ".agent-flow" / "skills"
    return Path.cwd() / ".agent-flow" / "skills"


def _skill_file(name: str, scope: str) -> Path:
    return _root(scope) / name / "SKILL.md"


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
@click.option("--scope", default="project", type=click.Choice(["project", "global"]))
def create_cmd(name: str, trigger: str, procedure: str, rules: str, abstraction: str, confidence: float, scope: str) -> None:
    path = _skill_file(name, scope)
    if path.exists():
        click.echo(f"Error: skill already exists: {name}", err=True)
        raise SystemExit(1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"name: {name}",
                f"trigger: {trigger}",
                f"confidence: {confidence}",
                f"abstraction: {abstraction}",
                "---",
                "## Procedure",
                procedure,
                "",
                "## Rules",
                rules,
                "",
            ]
        ),
        encoding="utf-8",
    )
    click.echo(f"Created skill: {name}")


@cli.command("edit")
@click.option("--name", required=True)
@click.option("--procedure", default=None)
@click.option("--rules", default=None)
@click.option("--scope", default="project", type=click.Choice(["project", "global"]))
def edit_cmd(name: str, procedure: str | None, rules: str | None, scope: str) -> None:
    path = _skill_file(name, scope)
    if not path.exists():
        click.echo(f"Error: skill not found: {name}", err=True)
        raise SystemExit(1)
    content = path.read_text(encoding="utf-8")
    if procedure is not None:
        content += f"\n# Procedure Update\n{procedure}\n"
    if rules is not None:
        content += f"\n# Rules Update\n{rules}\n"
    path.write_text(content, encoding="utf-8")
    click.echo(f"Edited skill: {name}")


@cli.command("patch")
@click.option("--name", required=True)
@click.option("--field", multiple=True)
@click.option("--scope", default="project", type=click.Choice(["project", "global"]))
def patch_cmd(name: str, field: tuple[str, ...], scope: str) -> None:
    path = _skill_file(name, scope)
    if not path.exists():
        click.echo(f"Error: skill not found: {name}", err=True)
        raise SystemExit(1)
    lines = path.read_text(encoding="utf-8").splitlines()
    for pair in field:
        lines.insert(0, pair)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(f"Patched skill: {name}")


@cli.command("delete")
@click.option("--name", required=True)
@click.option("--scope", default="project", type=click.Choice(["project", "global"]))
def delete_cmd(name: str, scope: str) -> None:
    path = _skill_file(name, scope)
    if not path.exists():
        click.echo(f"Skill '{name}' not found.", err=True)
        raise SystemExit(1)
    path.unlink()
    click.echo(f"Deleted skill: {name}")


@cli.command("list")
@click.option("--scope", default="project", type=click.Choice(["project", "global"]))
def list_cmd(scope: str) -> None:
    root = _root(scope)
    if not root.exists():
        click.echo("No skills found.")
        return
    for skill_file in sorted(root.rglob("SKILL.md")):
        click.echo(str(skill_file.parent.relative_to(root)))


@cli.command("show")
@click.option("--name", required=True)
@click.option("--scope", default="project", type=click.Choice(["project", "global"]))
def show_cmd(name: str, scope: str) -> None:
    path = _skill_file(name, scope)
    if not path.exists():
        click.echo(f"Error: skill not found: {name}", err=True)
        raise SystemExit(1)
    click.echo(path.read_text(encoding="utf-8"))
