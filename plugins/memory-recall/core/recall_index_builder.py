"""Recall index builder — Markdown rendering helpers for scene summaries.

Generates and renders the scene summary Markdown files and the recall INDEX.md.
"""

from agent_flow.core.recall_models import SceneSummary


def build_recall_entry_markdown(summary: SceneSummary) -> str:
    """Render a SceneSummary as a Markdown file with YAML frontmatter."""
    frontmatter = {
        "id": summary.id,
        "date": summary.date,
        "task": summary.task_description,
        "phases": summary.phases_completed,
        "decisions": summary.key_decisions,
        "experiences": summary.experiences_extracted,
        "skills_created": summary.skills_created,
        "wiki_created": summary.wiki_entries_created,
        "errors": summary.errors_encountered,
        "outcome": summary.outcome,
        "source_log": summary.source_log,
        "confidence": summary.confidence,
    }

    # Build YAML frontmatter
    import yaml

    fm_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True)

    # Build readable body
    parts = [
        f"# Session: {summary.id} ({summary.date})",
        "",
        f"## Task",
        summary.task_description or "(no description)",
        "",
    ]

    if summary.key_decisions:
        parts.append("## Key Decisions")
        for d in summary.key_decisions:
            parts.append(f"- {d}")
        parts.append("")

    if summary.experiences_extracted:
        parts.append("## Experiences Extracted")
        for e in summary.experiences_extracted:
            parts.append(f"- {e}")
        parts.append("")

    if summary.errors_encountered:
        parts.append("## Errors Encountered")
        for e in summary.errors_encountered:
            parts.append(f"- {e}")
        parts.append("")

    parts.append("## Outcome")
    parts.append(summary.outcome or "unknown")
    parts.append("")

    return f"---\n{fm_str}---\n\n" + "\n".join(parts)


def build_recall_index_markdown(entries: list[SceneSummary]) -> str:
    """Render the full recall INDEX.md with categorized entries."""
    parts = [
        "# Recall Index (Cross-session Summaries)",
        "",
        "## Recent Sessions",
        "| Date | Task | Outcome | ID |",
        "|------|------|---------|-----|",
    ]

    for entry in entries:
        task_short = entry.task_description[:50] + ("..." if len(entry.task_description) > 50 else "")
        parts.append(
            f"| {entry.date} | {task_short} | {entry.outcome} | [{entry.id}]({entry.id}.md) |"
        )

    parts.append("")

    # Group by module (extracted from experiences)
    by_module: dict[str, list[SceneSummary]] = {}
    for entry in entries:
        modules = set()
        for exp in entry.experiences_extracted:
            # Extract module from "module:xxx | ..." pattern
            if "module:" in exp:
                mod = exp.split("module:")[1].split("|")[0].strip()
                modules.add(mod)
        if not modules:
            modules.add("other")

        for mod in modules:
            by_module.setdefault(mod, []).append(entry)

    if by_module:
        parts.append("## By Module")
        for mod in sorted(by_module.keys()):
            parts.append(f"### {mod}")
            for entry in by_module[mod]:
                parts.append(f"- [{entry.id}]({entry.id}.md) - {entry.task_description[:60]}")
            parts.append("")

    # Group by outcome
    by_outcome: dict[str, list[SceneSummary]] = {}
    for entry in entries:
        by_outcome.setdefault(entry.outcome or "unknown", []).append(entry)

    if by_outcome:
        parts.append("## By Outcome")
        for outcome in sorted(by_outcome.keys()):
            parts.append(f"### {outcome}")
            for entry in by_outcome[outcome]:
                parts.append(f"- [{entry.id}]({entry.id}.md)")
            parts.append("")

    return "\n".join(parts)


def extract_searchable_text(summary: SceneSummary) -> str:
    """Concatenate all searchable fields into a single string for keyword matching."""
    parts = [
        summary.task_description,
        " ".join(summary.key_decisions),
        " ".join(summary.experiences_extracted),
        " ".join(summary.skills_created),
        " ".join(summary.errors_encountered),
        summary.outcome,
    ]
    return " ".join(p for p in parts if p)
