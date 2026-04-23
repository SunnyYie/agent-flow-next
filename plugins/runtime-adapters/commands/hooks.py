from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.claude_settings import ensure_project_claude_hooks


@click.group("hooks")
def cli() -> None:
    pass


@cli.command("setup-claude")
def setup_claude_cmd() -> None:
    settings_path, added = ensure_project_claude_hooks(Path.cwd())
    click.echo(f"{settings_path} (added {added} hooks)")
