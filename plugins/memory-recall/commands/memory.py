from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import click


def _path(project: Path) -> Path:
    return project / ".agent-flow" / "memory" / "entries.jsonl"


def _load(project: Path) -> list[dict]:
    path = _path(project)
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def _save(project: Path, rows: list[dict]) -> None:
    path = _path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text((text + "\n") if text else "", encoding="utf-8")


@click.group("memory")
def cli() -> None:
    pass


@cli.command("compress")
@click.option("--text", default="")
def compress_cmd(text: str) -> None:
    content = text.strip() or "manual memory snapshot"
    project = Path.cwd()
    rows = _load(project)
    rows.append({"id": len(rows) + 1, "time": datetime.now().isoformat(timespec="seconds"), "text": content})
    _save(project, rows)
    click.echo(f"Compressed memory entry #{len(rows)}")


@cli.command("index")
def index_cmd() -> None:
    click.echo("Memory index refreshed")


@cli.command("search")
@click.option("--query", "query", required=True)
def search_cmd(query: str) -> None:
    rows = _load(Path.cwd())
    matched = [row for row in rows if query.lower() in str(row.get("text", "")).lower()]
    if not matched:
        click.echo("No matched memory entries")
        return
    for row in matched:
        click.echo(f"[{row['id']}] {row['text']}")


@cli.command("get")
@click.argument("entry_id", type=int)
def get_cmd(entry_id: int) -> None:
    rows = _load(Path.cwd())
    for row in rows:
        if int(row.get("id", -1)) == entry_id:
            click.echo(json.dumps(row, ensure_ascii=False, indent=2))
            return
    click.echo(f"Entry {entry_id} not found")
    raise SystemExit(1)


@cli.command("stats")
def stats_cmd() -> None:
    rows = _load(Path.cwd())
    click.echo(f"entries: {len(rows)}")
