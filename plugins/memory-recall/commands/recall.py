from __future__ import annotations

from pathlib import Path

import click


def _recall_files(project: Path) -> list[Path]:
    files: list[Path] = []
    for base in [project / ".agent-flow" / "wiki" / "recall", project / ".dev-workflow" / "wiki" / "recall"]:
        if base.exists():
            files.extend(sorted(base.rglob("*.md")))
    return files


@click.command("recall")
@click.option("--query", "query", default="")
@click.option("--recent", "recent", default=0, type=int)
@click.option("--backtrack", "backtrack", default="")
def cli(query: str, recent: int, backtrack: str) -> None:
    files = _recall_files(Path.cwd())
    if backtrack:
        for path in files:
            if backtrack in path.stem:
                click.echo(path.read_text(encoding="utf-8"))
                return
        click.echo(f"Summary '{backtrack}' not found.")
        raise SystemExit(1)

    if recent > 0:
        for path in files[-recent:]:
            click.echo(f"[{path.stem}] {path}")
        return

    if query:
        found = [path for path in files if query.lower() in path.read_text(encoding="utf-8", errors="ignore").lower()]
        for path in found:
            click.echo(f"[{path.stem}] {path}")
        if not found:
            click.echo(f"No sessions found matching '{query}'.")
        return

    for path in files[-3:]:
        click.echo(f"[{path.stem}] {path}")
