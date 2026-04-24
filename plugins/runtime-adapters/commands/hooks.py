from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.claude_settings import ensure_project_claude_hooks
from agent_flow.core.runtime_context import (
    RuntimeContext,
    collect_runtime_context,
    render_runtime_context,
)


@click.group("hooks")
def cli() -> None:
    pass


@cli.command("setup-claude")
def setup_claude_cmd() -> None:
    """Set up Claude Code hooks for the current project."""
    settings_path, added = ensure_project_claude_hooks(Path.cwd())
    click.echo(f"{settings_path} (added {added} hooks)")


@cli.command("inject-context")
@click.option("--event", default="startup-context", help="Event type for context collection.")
@click.option("--target", type=click.Choice(["claude-hook", "executor-system", "doctor"]), default="claude-hook")
@click.option("--diff", "diff_mode", is_flag=True, help="Only inject changed context (diff mode).")
def inject_context_cmd(event: str, target: str, diff_mode: bool) -> None:
    """Inject runtime context for the current project."""
    project_dir = Path.cwd()
    prompt = ""
    context = collect_runtime_context(project_dir, prompt, event=event)
    rendered = render_runtime_context(project_dir, context, target=target, diff_mode=diff_mode)
    if rendered:
        click.echo(rendered)
    else:
        click.echo("(no context changes)")
