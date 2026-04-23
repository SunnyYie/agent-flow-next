from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click


def _path(project: Path) -> Path:
    return project / ".agent-flow" / "state" / "user-profile.json"


def _default() -> dict:
    return {
        "user_id": "local-user",
        "created": datetime.now().isoformat(timespec="seconds"),
        "last_updated": "",
        "observation_count": 0,
        "tech_stack": {"avoidance_list": []},
        "autonomy": {"level": 3, "description": "balanced"},
    }


def _load(project: Path) -> dict:
    path = _path(project)
    if not path.exists():
        return _default()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else _default()
    except Exception:
        return _default()


def _save(project: Path, data: dict) -> None:
    data["last_updated"] = datetime.now().isoformat(timespec="seconds")
    path = _path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@click.group("user")
def cli() -> None:
    pass


@cli.command("show")
def show_cmd() -> None:
    profile = _load(Path.cwd())
    click.echo(json.dumps(profile, ensure_ascii=False, indent=2))


@cli.command("set-autonomy")
@click.argument("level", type=click.IntRange(1, 5))
def set_autonomy_cmd(level: int) -> None:
    project = Path.cwd()
    profile = _load(project)
    profile.setdefault("autonomy", {})["level"] = level
    profile["autonomy"]["description"] = {1: "manual", 2: "low", 3: "balanced", 4: "high", 5: "auto"}[level]
    _save(project, profile)
    click.echo(f"Autonomy level set to {level}/5")


@cli.command("add-avoidance")
@click.argument("tool_or_framework")
def add_avoidance_cmd(tool_or_framework: str) -> None:
    project = Path.cwd()
    profile = _load(project)
    stack = profile.setdefault("tech_stack", {})
    avoid = stack.setdefault("avoidance_list", [])
    if tool_or_framework not in avoid:
        avoid.append(tool_or_framework)
    _save(project, profile)
    click.echo(f"Added '{tool_or_framework}' to avoidance list")


@cli.command("observe")
def observe_cmd() -> None:
    project = Path.cwd()
    profile = _load(project)
    profile["observation_count"] = int(profile.get("observation_count", 0)) + 1
    _save(project, profile)
    click.echo("Observed recent sessions and updated profile")
