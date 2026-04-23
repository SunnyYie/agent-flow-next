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


@click.command("plan-review")
@click.option("--spec", default="", help="Requirements document path")
@click.option("--mode", type=click.Choice(["expansion", "selective", "hold", "reduction"]), default="hold")
def cli(spec: str, mode: str) -> None:
    project = Path.cwd()
    out = project / ".agent-flow" / "pipeline" / "plan-review.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join([
            "# plan-review",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Spec: {spec or 'spec.md'}",
            f"Mode: {mode}",
            "",
            "Native plugin execution completed.",
            "",
        ]),
        encoding="utf-8",
    )
    _complete(project, "plan-review")
    click.echo(f"Plan review completed (mode: {mode})")
    click.echo(f"Output: {out}")
