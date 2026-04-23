from __future__ import annotations

from pathlib import Path

import click


@click.group("hermes")
def cli() -> None:
    """Native hermes utilities."""


@cli.command("status")
def status_cmd() -> None:
    click.echo("Hermes native mode: enabled")


@cli.command("snapshot")
@click.option("--name", default="latest")
def snapshot_cmd(name: str) -> None:
    path = Path.cwd() / ".agent-flow" / "memory" / "snapshots" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Snapshot {name}\n", encoding="utf-8")
    click.echo(f"Snapshot created: {path}")


@cli.command("search")
@click.argument("query")
def search_cmd(query: str) -> None:
    base = Path.cwd() / ".agent-flow"
    results = []
    if base.exists():
        for path in base.rglob("*.md"):
            if query.lower() in path.read_text(encoding="utf-8", errors="ignore").lower():
                results.append(path)
    if not results:
        click.echo("No matches")
        return
    for path in results[:20]:
        click.echo(str(path))


@cli.command("hooks")
def hooks_cmd() -> None:
    click.echo("Hermes hooks: on_turn_start, on_pre_compress, on_session_end")
