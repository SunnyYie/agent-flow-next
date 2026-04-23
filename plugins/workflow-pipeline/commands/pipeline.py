from __future__ import annotations

from pathlib import Path

import click
import yaml

STAGES = [
    "plan-review",
    "plan-eng-review",
    "add-feature",
    "run",
    "review",
    "qa",
    "ship",
]


def _state_path(project_dir: Path) -> Path:
    return project_dir / ".agent-flow" / "state" / "pipeline-state.yaml"


def _default_state() -> dict:
    return {
        "stages": {stage: "pending" for stage in STAGES},
    }


def _load_state(project_dir: Path) -> dict:
    state_file = _state_path(project_dir)
    if not state_file.exists():
        return _default_state()
    data = yaml.safe_load(state_file.read_text(encoding="utf-8")) or {}
    stages = data.get("stages")
    if not isinstance(stages, dict):
        return _default_state()
    merged = _default_state()
    for stage in STAGES:
        status = stages.get(stage)
        if status in {"pending", "completed"}:
            merged["stages"][stage] = status
    return merged


def _save_state(project_dir: Path, state: dict) -> None:
    state_file = _state_path(project_dir)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")


def _index_of(stage: str) -> int:
    if stage not in STAGES:
        raise click.ClickException(f"unsupported stage: {stage}")
    return STAGES.index(stage)


@click.group(name="pipeline")
def cli() -> None:
    """Pipeline workflow commands."""


@cli.command("status")
def status_cmd() -> None:
    state = _load_state(Path.cwd())
    for stage in STAGES:
        click.echo(f"{stage}\t{state['stages'][stage]}")


@cli.command("run")
@click.option("--to-stage", default="", help="Run stages up to (and including) this stage")
def run_cmd(to_stage: str) -> None:
    project = Path.cwd()
    state = _load_state(project)

    end_idx = _index_of(to_stage) if to_stage else len(STAGES) - 1
    for stage in STAGES[: end_idx + 1]:
        state["stages"][stage] = "completed"
        click.echo(f"completed stage: {stage}")

    _save_state(project, state)


@cli.command("resume")
@click.option("--from-stage", default="", help="Resume execution from this stage")
def resume_cmd(from_stage: str) -> None:
    project = Path.cwd()
    state = _load_state(project)

    start_idx = _index_of(from_stage) if from_stage else 0
    for stage in STAGES[start_idx:]:
        state["stages"][stage] = "completed"
        click.echo(f"completed stage: {stage}")

    _save_state(project, state)
