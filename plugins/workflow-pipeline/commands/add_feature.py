from __future__ import annotations

import re
import subprocess
from pathlib import Path

import click

from agent_flow.core.pipeline_state import PipelineManager


def _slugify(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-")
    return value or "feature"


@click.command("add-feature")
@click.argument("name")
def cli(name: str) -> None:
    project = Path.cwd()
    manager = PipelineManager(project)
    state = manager.load_state()
    branch = f"feat/{_slugify(name)}"

    if (project / ".git").exists():
        result = subprocess.run(["git", "checkout", "-b", branch], cwd=project, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            click.echo(f"git checkout failed: {result.stderr.strip() or result.stdout.strip()}", err=True)
            raise SystemExit(1)

    marker = project / ".agent-flow" / "state" / "current-feature.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(f"name={name}\nbranch={branch}\n", encoding="utf-8")

    if not state.id:
        manager.init_pipeline(feature_name=name, branch=branch)
    else:
        state.feature_name = state.feature_name or name
        state.branch = branch
        manager.save_state(state)
    manager.complete_stage("add-feature", output=branch)
    click.echo(f"Feature branch ready: {branch}")
