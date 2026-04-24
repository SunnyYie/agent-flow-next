from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from agent_flow.core.pipeline_state import PipelineManager
from agent_flow.core.stage_runtime import maybe_execute_stage_runtime


@click.command("review")
@click.option("--auto-run", is_flag=True)
@click.option("--prompt-only", is_flag=True)
@click.option(
    "--backend",
    type=click.Choice(["command", "agent-scheduler", "orchestrator", "orchestrator+agent-scheduler", "claude-native"]),
    default=None,
)
def cli(auto_run: bool, prompt_only: bool, backend: str | None) -> None:
    project = Path.cwd()
    manager = PipelineManager(project)
    manager.start_stage("review")
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
    runtime = maybe_execute_stage_runtime(
        project,
        "review",
        out,
        metadata=[],
        cli_auto_run=auto_run or None,
        cli_prompt_only=prompt_only,
        cli_backend=backend,
    )
    manager.complete_stage("review", verdict="approved", output=out.name)
    click.echo(f"Review completed: {out}")
    if runtime.attempted and not runtime.executed:
        click.echo(f"Runtime fallback: {runtime.fallback_reason}")
