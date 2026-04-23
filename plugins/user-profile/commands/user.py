from __future__ import annotations

import json
from pathlib import Path

import click

from agent_flow.core.recall import RecallManager
from agent_flow.core.user_model import UserModelManager


@click.group("user")
def cli() -> None:
    pass


@cli.command("show")
def show_cmd() -> None:
    manager = UserModelManager()
    profile = manager.load_profile()
    click.echo(json.dumps(profile.model_dump(), ensure_ascii=False, indent=2))


@cli.command("set-autonomy")
@click.argument("level", type=click.IntRange(1, 5))
def set_autonomy_cmd(level: int) -> None:
    manager = UserModelManager()
    manager.set_autonomy(level)
    click.echo(f"Autonomy level set to {level}/5")


@cli.command("add-avoidance")
@click.argument("tool_or_framework")
def add_avoidance_cmd(tool_or_framework: str) -> None:
    manager = UserModelManager()
    manager.add_avoidance(tool_or_framework)
    click.echo(f"Added '{tool_or_framework}' to avoidance list")


@cli.command("observe")
def observe_cmd() -> None:
    manager = UserModelManager()
    recall_manager = RecallManager(Path.cwd())
    summaries = recall_manager.get_recent_summaries(1)
    if not summaries:
        click.echo("No recall summaries found; observation skipped.")
        raise SystemExit(1)
    manager.observe_session(summaries[0])
    click.echo(f"Observed summary: {summaries[0].id}")
