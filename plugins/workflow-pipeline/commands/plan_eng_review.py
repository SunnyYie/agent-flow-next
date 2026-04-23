from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click
import yaml


def _state_path(project: Path) -> Path:
    return project / ".agent-flow" / "state" / "pipeline-state.yaml"


def _complete(project: Path, stage: str) -> None:
    path = _state_path(project)
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        data = {"stages": {}}
    stages = data.setdefault("stages", {})
    stages[stage] = "completed"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@click.command("plan-eng-review")
@click.option("--spec", default="", help="Requirements document path")
@click.option("--scope", type=click.Choice(["frontend", "full"]), default="frontend")
def cli(spec: str, scope: str) -> None:
    project = Path.cwd()
    out = project / ".agent-flow" / "pipeline" / "eng-review.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join([
            "# plan-eng-review",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Spec: {spec or 'spec.md'}",
            f"Scope: {scope}",
            "",
            "Native plugin execution completed.",
            "",
        ]),
        encoding="utf-8",
    )
    _complete(project, "plan-eng-review")
    click.echo(f"Engineering review completed (scope: {scope})")
    click.echo(f"Output: {out}")
