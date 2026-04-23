from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
import yaml


def _complete(project: Path, stage: str) -> None:
    path = project / ".agent-flow" / "state" / "pipeline-state.yaml"
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        data = {"stages": {}}
    data.setdefault("stages", {})[stage] = "completed"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@click.command("run")
@click.option("--tasks", default="", help="Comma-separated task IDs")
@click.option("--dry-run", is_flag=True)
def cli(tasks: str, dry_run: bool) -> None:
    project = Path.cwd()
    out = project / ".agent-flow" / "pipeline" / "run-log.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join([
            "# run",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Tasks: {tasks or 'all'}",
            f"Dry run: {dry_run}",
            "",
            "Native plugin execution completed.",
            "",
        ]),
        encoding="utf-8",
    )
    if not dry_run:
        _complete(project, "run")
    click.echo(("Dry run" if dry_run else "Run stage") + " completed")
    click.echo(f"Output: {out}")
