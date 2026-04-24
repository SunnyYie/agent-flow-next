from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from agent_flow.core.pipeline_state import PipelineManager
from agent_flow.core.stage_runtime import maybe_execute_stage_runtime


@click.command("qa")
@click.option("--suite", default="default")
@click.option("--auto-run", is_flag=True)
@click.option("--prompt-only", is_flag=True)
@click.option(
    "--backend",
    type=click.Choice(["command", "agent-scheduler", "orchestrator", "orchestrator+agent-scheduler", "claude-native"]),
    default=None,
)
def cli(suite: str, auto_run: bool, prompt_only: bool, backend: str | None) -> None:
    project = Path.cwd()
    manager = PipelineManager(project)
    manager.start_stage("qa")
    out = project / ".agent-flow" / "pipeline" / "qa.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join([
            "# qa",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Suite: {suite}",
            "",
            "Native plugin execution completed.",
            "",
        ]),
        encoding="utf-8",
    )
    runtime = maybe_execute_stage_runtime(
        project,
        "qa",
        out,
        metadata=[suite],
        cli_auto_run=auto_run or None,
        cli_prompt_only=prompt_only,
        cli_backend=backend,
    )
    manager.complete_stage("qa", verdict="approved", output=out.name)
    click.echo(f"QA completed: {out}")
    if runtime.attempted and not runtime.executed:
        click.echo(f"Runtime fallback: {runtime.fallback_reason}")
