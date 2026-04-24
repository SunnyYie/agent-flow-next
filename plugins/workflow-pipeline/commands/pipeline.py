from __future__ import annotations

from pathlib import Path

import click
import yaml

from agent_flow.core.pipeline_state import PIPELINE_STAGE_ORDER, PipelineManager


def _index_of(stage: str) -> int:
    if stage not in PIPELINE_STAGE_ORDER:
        raise click.ClickException(f"unsupported stage: {stage}")
    return PIPELINE_STAGE_ORDER.index(stage)


def _sync_legacy_state(project: Path, manager: PipelineManager) -> None:
    """Keep legacy pipeline-state.yaml in sync for compatibility/tests."""
    state = manager.load_state()
    path = project / ".agent-flow" / "state" / "pipeline-state.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "stages": {
            stage: (state.stages.get(stage).status.value if state.stages.get(stage) else "pending")
            for stage in PIPELINE_STAGE_ORDER
        }
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@click.group(name="pipeline")
def cli() -> None:
    """Pipeline workflow commands."""


@cli.command("status")
def status_cmd() -> None:
    manager = PipelineManager(Path.cwd())
    state = manager.load_state()
    for stage in PIPELINE_STAGE_ORDER:
        stage_state = state.stages.get(stage)
        status = stage_state.status.value if stage_state else "pending"
        click.echo(f"{stage}\t{status}")


@cli.command("run")
@click.option("--to-stage", default="", help="Run stages up to (and including) this stage")
def run_cmd(to_stage: str) -> None:
    project = Path.cwd()
    manager = PipelineManager(project)
    end_idx = _index_of(to_stage) if to_stage else len(PIPELINE_STAGE_ORDER) - 1
    for stage in PIPELINE_STAGE_ORDER[: end_idx + 1]:
        manager.complete_stage(stage, output=f"{stage}.md")
        click.echo(f"completed stage: {stage}")
    _sync_legacy_state(project, manager)


@cli.command("resume")
@click.option("--from-stage", default="", help="Resume execution from this stage")
def resume_cmd(from_stage: str) -> None:
    project = Path.cwd()
    manager = PipelineManager(project)
    start_idx = _index_of(from_stage) if from_stage else 0
    for stage in PIPELINE_STAGE_ORDER[start_idx:]:
        manager.complete_stage(stage, output=f"{stage}.md")
        click.echo(f"completed stage: {stage}")
    _sync_legacy_state(project, manager)
