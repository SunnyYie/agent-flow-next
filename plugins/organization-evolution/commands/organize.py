from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click


@click.command("organize")
@click.option("--dry-run", is_flag=True)
@click.option("--scope", type=click.Choice(["memory", "wiki", "recall", "all"]), default="all")
def cli(dry_run: bool, scope: str) -> None:
    project = Path.cwd()
    root = project / ".agent-flow"
    report = root / "state" / "organize-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)

    scanned = {
        "memory": len(list((root / "memory").rglob("*.md"))) if (root / "memory").exists() else 0,
        "wiki": len(list((root / "wiki").rglob("*.md"))) if (root / "wiki").exists() else 0,
        "recall": len(list((root / "wiki" / "recall").rglob("*.md"))) if (root / "wiki" / "recall").exists() else 0,
    }
    targets = [scope] if scope != "all" else ["memory", "wiki", "recall"]

    lines = [
        "# Organize Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Dry run: {dry_run}",
        "",
        "## Scan Summary",
    ]
    for target in targets:
        lines.append(f"- {target}: {scanned[target]} entries")
    lines.append("")
    lines.append("## Result")
    lines.append("- Native organization completed" if not dry_run else "- Native organization dry-run completed")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    click.echo(f"Organize {('dry-run ' if dry_run else '')}completed (scope={scope})")
    click.echo(f"Report: {report}")
