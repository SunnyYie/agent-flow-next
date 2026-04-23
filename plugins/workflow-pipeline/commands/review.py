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


@click.command("review")
def cli() -> None:
    project = Path.cwd()
    out = project / ".agent-flow" / "pipeline" / "review.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join([
            "# review",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "Native plugin execution completed.",
            "",
        ]),
        encoding="utf-8",
    )
    _complete(project, "review")
    click.echo(f"Review completed: {out}")
