from __future__ import annotations

from pathlib import Path

import click

from agent_flow.core.organizer import MemoryOrganizer


@click.command("organize")
@click.option("--dry-run", is_flag=True, help="Show what would be organized without making changes")
@click.option("--force", is_flag=True, help="Run organization even if triggers are not met")
@click.option(
    "--scope",
    type=click.Choice(["memory", "wiki", "recall", "all"]),
    default="all",
    help="What to organize",
)
def cli(dry_run: bool, force: bool, scope: str) -> None:
    project_path = Path.cwd()
    organizer = MemoryOrganizer(project_path)

    if not force and not dry_run:
        triggers = organizer.check_triggers()
        if not triggers:
            click.echo("No organization triggers met. Use --force to run anyway.")
            click.echo("\nTrigger thresholds:")
            click.echo(f"  Memory entries: > {organizer.triggers.memory_entry_threshold}")
            click.echo(f"  Wiki index lines: > {organizer.triggers.wiki_index_line_threshold}")
            click.echo(f"  Recall summaries: > {organizer.triggers.recall_summary_threshold}")
            click.echo(f"  Days since last organize: > {organizer.triggers.days_since_last_organize}")
            return

    report = organizer.run_full_organization(dry_run=dry_run, force=force, scope=scope)

    if dry_run:
        click.echo("=== DRY RUN - No changes made ===\n")
    else:
        click.echo("=== Organization Complete ===\n")

    click.echo(f"Timestamp: {report.timestamp}")
    click.echo(f"Scope: {scope}")

    if report.memory_entries_scanned:
        click.echo(f"\nMemory entries scanned: {report.memory_entries_scanned}")
        click.echo(f"  Deprecated: {report.entries_deprecated}")
        click.echo(f"  Archived: {report.entries_archived}")
        click.echo(f"  Compressed: {report.entries_compressed}")

    if report.wiki_entries_scanned:
        click.echo(f"\nWiki changes: {report.wiki_entries_scanned}")

    if report.recall_entries_scanned:
        click.echo(f"\nRecall pruned: {report.recall_entries_scanned}")

    if report.decay_results:
        click.echo("\n--- Decay Details ---")
        for result in report.decay_results:
            if result.action != "keep":
                click.echo(f"  [{result.action.upper()}] {result.entry_header}")
                click.echo(f"    Reason: {result.reason}")
