from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.recall import RecallManager


@click.command("recall")
@click.option("--query", "query", default="")
@click.option("--recent", "recent", default=0, type=int)
@click.option("--backtrack", "backtrack", default="")
def cli(query: str, recent: int, backtrack: str) -> None:
    manager = RecallManager(Path.cwd())

    if backtrack:
        _handle_backtrack(manager, backtrack)
        return

    if recent > 0:
        _handle_recent(manager, recent)
        return

    if query:
        _handle_query(manager, query)
        return

    _handle_recent(manager, 3)


def _handle_recent(manager: RecallManager, n: int) -> None:
    summaries = manager.get_recent_summaries(n)
    if not summaries:
        click.echo("No session summaries found. Summaries are created during REFLECT phase.")
        return
    click.echo(f"Recent {len(summaries)} session summaries:\n")
    for summary in summaries:
        click.echo(f"[{summary.id}] {summary.date} — {summary.task_description[:60]}")
        click.echo(f"  Outcome: {summary.outcome} | Confidence: {summary.confidence}")


def _handle_query(manager: RecallManager, query: str) -> None:
    summaries = manager.search_summaries(query)
    if not summaries:
        click.echo(f"No sessions found matching '{query}'.")
        return
    click.echo(f"Found {len(summaries)} sessions matching '{query}':\n")
    for summary in summaries:
        click.echo(f"[{summary.id}] {summary.date} — {summary.task_description[:60]}")
        click.echo(f"  Outcome: {summary.outcome} | Confidence: {summary.confidence}")


def _handle_backtrack(manager: RecallManager, summary_id: str) -> None:
    recall_dir = manager._active_recall_dir()
    summary_file = recall_dir / f"{summary_id}.md"
    if not summary_file.is_file():
        click.echo(f"Summary '{summary_id}' not found.")
        raise SystemExit(1)

    summary = RecallManager._parse_summary_file(summary_file)
    if summary is None:
        click.echo(f"Failed to parse summary '{summary_id}'.")
        raise SystemExit(1)

    click.echo(f"=== Summary: {summary.id} ===")
    click.echo(f"Date: {summary.date}")
    click.echo(f"Task: {summary.task_description}")
    click.echo(f"Outcome: {summary.outcome}")
    click.echo("")

    source_content = manager.backtrack_to_source(summary)
    if source_content:
        click.echo(f"--- Source: {summary.source_log} ---\n")
        lines = source_content.split("\n")
        if len(lines) > 100:
            click.echo(f"(Showing last 100 of {len(lines)} lines)\n")
            lines = lines[-100:]
        click.echo("\n".join(lines))
    else:
        click.echo(f"Source log not available: {summary.source_log}")
