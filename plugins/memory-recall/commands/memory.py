from __future__ import annotations

import sqlite3
from pathlib import Path

import click

from agent_flow.core.compression import compress_all
from agent_flow.core.memory import MemoryManager
from agent_flow.core.memory_index import ensure_index_ready, search_index


def _db_path(project: Path) -> Path:
    return project / ".agent-flow" / "observations.db"


def _ensure_observations_schema(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS observations (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                file_path TEXT,
                observation_type TEXT,
                tool_input_summary TEXT,
                compressed INTEGER DEFAULT 0,
                summary_id TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@click.group("memory")
def cli() -> None:
    pass


@cli.command("compress")
@click.option("--text", default="")
def compress_cmd(text: str) -> None:
    project = Path.cwd()
    db_path = _db_path(project)
    _ensure_observations_schema(db_path)

    if text.strip():
        MemoryManager(project).append_memory(text.strip())

    count = compress_all(str(db_path))
    click.echo(f"Compressed observations: {count}")


@cli.command("index")
def index_cmd() -> None:
    project = Path.cwd()
    count, status = ensure_index_ready(project, str(_db_path(project)))
    click.echo(f"Memory index ready: {count} entries ({status})")


@cli.command("search")
@click.option("--query", "query", required=True)
@click.option("--source-type", default="", help="Filter by source type (soul/wiki/recall/skill)")
@click.option("--limit", default=20, type=int)
def search_cmd(query: str, source_type: str, limit: int) -> None:
    project = Path.cwd()
    db = _db_path(project)
    count, _status = ensure_index_ready(project, str(db))
    if count == 0:
        click.echo("No indexed memory entries yet")
        return
    rows = search_index(str(db), query=query, source_type=(source_type or None), limit=limit)
    if not rows:
        # Fallback for environments where FTS virtual table is not yet populated.
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            sql = (
                "SELECT * FROM memory_index "
                "WHERE (title LIKE ? OR content_summary LIKE ?) "
            )
            params = [f"%{query}%", f"%{query}%"]
            if source_type:
                sql += "AND source_type = ? "
                params.append(source_type)
            sql += "ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()
    if not rows:
        click.echo("No matched memory entries")
        return
    for row in rows:
        click.echo(
            f"[{row.get('id','')}] {row.get('source_type','')} {row.get('title','').strip()} :: {row.get('source_path','')}"
        )


@cli.command("get")
@click.argument("entry_id")
def get_cmd(entry_id: str) -> None:
    project = Path.cwd()
    db = _db_path(project)
    count, _status = ensure_index_ready(project, str(db))
    if count == 0:
        click.echo("No indexed memory entries yet")
        raise SystemExit(1)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM memory_index WHERE id = ?", (entry_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        click.echo(f"Entry {entry_id} not found")
        raise SystemExit(1)
    click.echo(f"id: {row['id']}")
    click.echo(f"source_type: {row['source_type']}")
    click.echo(f"title: {row['title']}")
    click.echo(f"source_path: {row['source_path']}")
    click.echo(f"summary: {row['content_summary']}")


@cli.command("stats")
def stats_cmd() -> None:
    project = Path.cwd()
    db = _db_path(project)
    count, status = ensure_index_ready(project, str(db))
    if count == 0:
        click.echo("entries: 0")
        return

    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT source_type, COUNT(*) AS cnt FROM memory_index GROUP BY source_type ORDER BY source_type"
        ).fetchall()
    finally:
        conn.close()
    click.echo(f"entries: {count} ({status})")
    for source_type, c in rows:
        click.echo(f"- {source_type}: {c}")
