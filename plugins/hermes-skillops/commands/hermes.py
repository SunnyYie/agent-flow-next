from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.evolution import export_skill_tree
from agent_flow.core.frozen_memory import FrozenMemoryManager

@click.group("hermes")
def cli() -> None:
    """Native hermes utilities."""


@cli.command("status")
def status_cmd() -> None:
    manager = FrozenMemoryManager(Path.cwd())
    snapshot = manager.load_snapshot()
    click.echo("Hermes native mode: enabled")
    click.echo(f"snapshot_checksum: {snapshot.checksum}")
    click.echo(f"skills_loaded: {len(snapshot.relevant_skills)}")
    click.echo(f"experiences_loaded: {len(snapshot.relevant_experiences)}")


@cli.command("snapshot")
@click.option("--name", default="latest")
def snapshot_cmd(name: str) -> None:
    manager = FrozenMemoryManager(Path.cwd())
    snapshot = manager.load_snapshot()
    content = manager.format_for_system_prompt(snapshot)
    path = Path.cwd() / ".agent-flow" / "memory" / "snapshots" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    click.echo(f"Snapshot created: {path}")


@cli.command("search")
@click.argument("query")
def search_cmd(query: str) -> None:
    manager = FrozenMemoryManager(Path.cwd())
    snapshot = manager.load_snapshot()
    lines = manager.format_for_system_prompt(snapshot).splitlines()
    results = [line for line in lines if query.lower() in line.lower()]
    if not results:
        click.echo("No matches")
        return
    for line in results[:20]:
        click.echo(line)


@cli.command("hooks")
def hooks_cmd() -> None:
    tree = export_skill_tree(Path.cwd())
    click.echo("Hermes hooks: on_turn_start, on_pre_compress, on_session_end, on_memory_write")
    click.echo(f"crystallized_skills: {len(tree)}")
