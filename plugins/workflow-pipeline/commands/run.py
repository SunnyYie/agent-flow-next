from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from agent_flow.core.pipeline_state import PipelineManager
from agent_flow.core.stage_runtime import maybe_execute_stage_runtime


@click.command("run")
@click.option("--tasks", default="", help="Comma-separated task IDs")
@click.option("--dry-run", is_flag=True)
@click.option("--auto-run", is_flag=True)
@click.option(
    "--backend",
    type=click.Choice(["command", "agent-scheduler", "orchestrator", "orchestrator+agent-scheduler", "claude-native"]),
    default=None,
)
def cli(tasks: str, dry_run: bool, auto_run: bool, backend: str | None) -> None:
    project = Path.cwd()
    manager = PipelineManager(project)
    manager.start_stage("run")
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
    runtime = maybe_execute_stage_runtime(
        project,
        "run",
        out,
        metadata=[tasks or "all", f"dry_run={dry_run}"],
        cli_auto_run=auto_run or None,
        cli_prompt_only=dry_run,
        cli_backend=backend,
    )
    if not dry_run:
        manager.complete_stage("run", output=out.name)
    click.echo(("Dry run" if dry_run else "Run stage") + " completed")
    click.echo(f"Output: {out}")
    if runtime.attempted and not runtime.executed:
        click.echo(f"Runtime fallback: {runtime.fallback_reason}")
