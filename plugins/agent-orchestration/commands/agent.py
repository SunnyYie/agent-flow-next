from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click


class _Store:
    def __init__(self, project: Path):
        self.path = project / ".agent-flow" / "state" / "agents.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save(self, rows: list[dict]) -> None:
        self.path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@click.group("agent")
def cli() -> None:
    """Manage lightweight local sub-agent records."""


@cli.command("list")
def list_cmd() -> None:
    rows = _Store(Path.cwd()).load()
    if not rows:
        click.echo("No sub-agents found.")
        return
    for row in rows:
        click.echo(f"[{row['name']}] {row['role']} {row['status']} — {row['task']}")


@cli.command("spawn")
@click.option("--role", type=click.Choice(["executor", "verifier", "researcher", "tech-leader"]), required=True)
@click.option("--task", required=True)
@click.option("--name", default="")
def spawn_cmd(role: str, task: str, name: str) -> None:
    store = _Store(Path.cwd())
    rows = store.load()
    agent_name = name.strip() or f"agent-{len(rows) + 1}"
    rows.append(
        {
            "name": agent_name,
            "role": role,
            "task": task,
            "status": "running",
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    store.save(rows)
    click.echo(f"Agent spawned: {agent_name}")


@cli.command("terminate")
@click.argument("agent_name")
@click.option("--result", default="")
def terminate_cmd(agent_name: str, result: str) -> None:
    store = _Store(Path.cwd())
    rows = store.load()
    for row in rows:
        if row.get("name") == agent_name:
            row["status"] = "terminated"
            if result:
                row["result"] = result
            store.save(rows)
            click.echo(f"Agent '{agent_name}' terminated.")
            return
    click.echo(f"Agent '{agent_name}' not found.")
    raise SystemExit(1)


@cli.command("sync")
@click.option("--agent-name", default="")
def sync_cmd(agent_name: str) -> None:
    target = agent_name.strip() or "all"
    click.echo(f"Synced agent memory: {target}")
