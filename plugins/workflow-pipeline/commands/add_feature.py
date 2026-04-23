from __future__ import annotations

import re
import subprocess
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


def _slugify(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-")
    return value or "feature"


@click.command("add-feature")
@click.argument("name")
def cli(name: str) -> None:
    project = Path.cwd()
    branch = f"feat/{_slugify(name)}"

    if (project / ".git").exists():
        result = subprocess.run(["git", "checkout", "-b", branch], cwd=project, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            click.echo(f"git checkout failed: {result.stderr.strip() or result.stdout.strip()}", err=True)
            raise SystemExit(1)

    marker = project / ".agent-flow" / "state" / "current-feature.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"name={name}\nbranch={branch}\n", encoding="utf-8")

    _complete(project, "add-feature")
    click.echo(f"Feature branch ready: {branch}")
