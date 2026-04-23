from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

PROPOSAL_TEMPLATE_FILENAME = "mcp-tool-factory-proposal.md"
MARKER_FILENAME = ".mcp-tool-factory-requested"


@click.group(name="mcp-factory")
def cli() -> None:
    """MCP tool-factory proposal and approval workflow."""


@cli.command("request")
@click.option("--project-dir", default=".", help="Project root directory")
@click.option("--task", default="", help="Task id/title, e.g. T2 or feature-name")
@click.option("--scope", type=click.Choice(["project", "global"]), default="project", help="Requested MCP scope")
@click.option("--summary", default="", help="Short request summary")
@click.option("--proposal-file", default="", help="Optional proposal file path")
def request_cmd(project_dir: str, task: str, scope: str, summary: str, proposal_file: str) -> None:
    root = Path(project_dir).resolve()
    state_dir = root / ".agent-flow" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    proposal_path = _resolve_proposal_path(root, proposal_file)
    if not proposal_path.exists():
        proposal_path.parent.mkdir(parents=True, exist_ok=True)
        proposal_path.write_text(_render_proposal_template(scope), encoding="utf-8")

    marker_path = state_dir / MARKER_FILENAME
    task_value = task.strip() or _resolve_task_hint(root)
    summary_value = summary.strip() or f"MCP tool factory request ({scope})"
    entry = {
        "phase": "reflect",
        "status": "pending",
        "timestamp": _now_iso(),
        "task": task_value,
        "confirmed_by": "pending",
        "summary": summary_value,
        "scope": scope,
        "proposal": _rel_or_abs(root, proposal_path),
    }
    entries = _read_marker_entries(marker_path)
    entries.append(entry)
    _write_marker_entries(marker_path, entries)

    click.echo("MCP tool-factory request recorded.")
    click.echo(f"Proposal: {proposal_path}")
    click.echo(f"Marker: {marker_path}")


@cli.command("approve")
@click.option("--project-dir", default=".", help="Project root directory")
@click.option("--task", default="", help="Only approve entries for this task")
@click.option("--confirmed-by", default="user", help="Approver identity")
@click.option("--summary", default="用户已明确同意创建 MCP Server", help="Approval summary")
def approve_cmd(project_dir: str, task: str, confirmed_by: str, summary: str) -> None:
    _resolve_marker_entries(
        project_dir=project_dir,
        task=task,
        confirmed_by=confirmed_by,
        summary=summary,
        decision="approved",
    )


@cli.command("reject")
@click.option("--project-dir", default=".", help="Project root directory")
@click.option("--task", default="", help="Only reject entries for this task")
@click.option("--confirmed-by", default="user", help="Reviewer identity")
@click.option("--summary", default="用户拒绝当前 MCP Server 创建提案", help="Rejection summary")
def reject_cmd(project_dir: str, task: str, confirmed_by: str, summary: str) -> None:
    _resolve_marker_entries(
        project_dir=project_dir,
        task=task,
        confirmed_by=confirmed_by,
        summary=summary,
        decision="rejected",
    )


def _resolve_marker_entries(*, project_dir: str, task: str, confirmed_by: str, summary: str, decision: str) -> None:
    root = Path(project_dir).resolve()
    state_dir = root / ".agent-flow" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    marker_path = state_dir / MARKER_FILENAME

    entries = _read_marker_entries(marker_path)
    if not entries:
        fallback_task = task.strip() or _resolve_task_hint(root)
        entries = [
            {
                "phase": "reflect",
                "status": decision,
                "timestamp": _now_iso(),
                "task": fallback_task,
                "confirmed_by": confirmed_by.strip() or "user",
                "summary": summary.strip() or f"MCP request {decision}",
            }
        ]
        _write_marker_entries(marker_path, entries)
        click.echo(f"No pending entries found; wrote a direct {decision} marker.")
        click.echo(f"Marker: {marker_path}")
        return

    pending_entries = [entry for entry in entries if not _entry_resolved(entry)]
    if not pending_entries:
        click.echo("No pending MCP factory request found; marker already resolved.")
        click.echo(f"Marker: {marker_path}")
        return

    task_filter = task.strip()
    updated = False
    for entry in pending_entries:
        if task_filter and entry.get("task", "").strip() != task_filter:
            continue
        entry["status"] = decision
        entry["timestamp"] = _now_iso()
        entry["confirmed_by"] = confirmed_by.strip() or "user"
        entry["summary"] = summary.strip() or entry.get("summary", f"MCP request {decision}")
        updated = True

    if not updated:
        click.echo("No matching pending entry for the provided task.")
        click.echo(f"Marker: {marker_path}")
        raise SystemExit(1)

    _write_marker_entries(marker_path, entries)
    click.echo(f"MCP tool-factory request {decision} and resolved.")
    click.echo(f"Marker: {marker_path}")


def _render_proposal_template(scope: str) -> str:
    return f"""# MCP Tool Factory Proposal

## Problem
- Describe where existing tools are inefficient.
- Include concrete task evidence.

## Current Workaround
- What workaround is being used now.
- Estimated cost (time/complexity/risk).

## Proposed MCP Server
- Name:
- Scope: {scope}
- Capability:
- Input/Output Contract:
"""


def _resolve_proposal_path(project_root: Path, proposal_file: str) -> Path:
    if proposal_file.strip():
        candidate = Path(proposal_file).expanduser()
        return candidate if candidate.is_absolute() else (project_root / candidate).resolve()
    return (project_root / ".agent-flow" / "state" / PROPOSAL_TEMPLATE_FILENAME).resolve()


def _resolve_task_hint(project_root: Path) -> str:
    phase_path = project_root / ".agent-flow" / "state" / "current_phase.md"
    if not phase_path.is_file():
        return "mcp-tool-factory"
    try:
        for line in phase_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("# 任务:"):
                return stripped.split(":", 1)[1].strip() or "mcp-tool-factory"
    except OSError:
        pass
    return "mcp-tool-factory"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _entry_resolved(entry: dict[str, str]) -> bool:
    return entry.get("status", "").strip().lower() in {
        "resolved",
        "closed",
        "done",
        "approved",
        "confirmed",
        "rejected",
        "declined",
        "cancelled",
    }


def _read_marker_entries(marker_path: Path) -> list[dict[str, str]]:
    if not marker_path.exists():
        return []
    blocks = marker_path.read_text(encoding="utf-8").strip().split("\n\n")
    entries: list[dict[str, str]] = []
    for block in blocks:
        if not block.strip():
            continue
        entry: dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            entry[key.strip()] = value.strip()
        if entry:
            entries.append(entry)
    return entries


def _write_marker_entries(marker_path: Path, entries: list[dict[str, str]]) -> None:
    body_blocks: list[str] = []
    for entry in entries:
        lines = [f"{key}: {value}" for key, value in entry.items()]
        body_blocks.append("\n".join(lines))
    marker_path.write_text(("\n\n".join(body_blocks) + "\n") if body_blocks else "", encoding="utf-8")


def _rel_or_abs(project_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
