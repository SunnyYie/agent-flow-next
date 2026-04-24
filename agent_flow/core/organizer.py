"""Memory organizer: active organization, decay, compression, and pruning.

Integrates with REFLECT phase and organize CLI to automatically organize memories
when trigger thresholds are met.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agent_flow.core.config import ensure_file
from agent_flow.core.decay import (
    compute_quality_score,
    should_archive,
    should_compress,
    should_deprecate,
)
from agent_flow.core.memory import MemoryManager
from agent_flow.core.recall import RecallManager

DEFAULT_WIKI_INDEX = (
    "# Wiki 知识导航\n\n"
    "## Patterns（成功模式）\n\n"
    "## Pitfalls（踩坑记录）\n\n"
    "## Concepts（核心概念）\n\n"
    "## Decisions（架构决策）\n"
)


class OrganizationTrigger(BaseModel):
    """Thresholds that trigger active organization."""

    memory_entry_threshold: int = 20
    wiki_index_line_threshold: int = 50
    recall_summary_threshold: int = 30
    days_since_last_organize: int = 7


class DecayResult(BaseModel):
    """Result of a single decay evaluation."""

    entry_header: str = ""
    old_confidence: float = 0.0
    new_confidence: float = 0.0
    action: str = "keep"  # keep|deprecate|archive|compress|skip
    reason: str = ""


class OrganizationReport(BaseModel):
    """Summary of an organization run."""

    timestamp: str = ""
    memory_entries_scanned: int = 0
    wiki_entries_scanned: int = 0
    recall_entries_scanned: int = 0
    entries_deprecated: int = 0
    entries_archived: int = 0
    entries_compressed: int = 0
    patterns_promoted: int = 0
    decay_results: list[DecayResult] = Field(default_factory=list)


class MemoryOrganizer:
    """Active organization engine: decay, compress, archive, and promote memories."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.memory_manager = MemoryManager(project_dir, "main")
        self.triggers = OrganizationTrigger()

    def check_triggers(self) -> list[str]:
        """Check all organization triggers. Returns list of triggered reasons."""
        triggered: list[str] = []

        entry_count = self._count_memory_entries()
        if entry_count > self.triggers.memory_entry_threshold:
            triggered.append(f"memory_entries={entry_count} (> {self.triggers.memory_entry_threshold})")

        wiki_index_path = self.project_dir / ".agent-flow" / "wiki" / "INDEX.md"
        ensure_file(wiki_index_path, DEFAULT_WIKI_INDEX)
        if wiki_index_path.is_file():
            line_count = len(wiki_index_path.read_text(encoding="utf-8").splitlines())
            if line_count > self.triggers.wiki_index_line_threshold:
                triggered.append(
                    f"wiki_index_lines={line_count} (> {self.triggers.wiki_index_line_threshold})"
                )

        recall_manager = RecallManager(self.project_dir)
        summaries = recall_manager.get_recent_summaries(1000)
        if len(summaries) > self.triggers.recall_summary_threshold:
            triggered.append(
                f"recall_summaries={len(summaries)} (> {self.triggers.recall_summary_threshold})"
            )

        log_path = self.project_dir / ".agent-flow" / "logs" / "organization_log.md"
        if log_path.is_file():
            content = log_path.read_text(encoding="utf-8")
            last_organize = ""
            for line in reversed(content.splitlines()):
                if "[ORGANIZE]" in line:
                    parts = line.split("[ORGANIZE]")
                    if len(parts) > 1:
                        last_organize = parts[1].strip()[:10]
                    break

            if last_organize:
                try:
                    last_date = datetime.strptime(last_organize, "%Y-%m-%d")
                    days_since = (datetime.now() - last_date).days
                    if days_since > self.triggers.days_since_last_organize:
                        triggered.append(
                            f"days_since_last_organize={days_since} "
                            f"(> {self.triggers.days_since_last_organize})"
                        )
                except ValueError:
                    pass
        else:
            triggered.append("never_organized")

        return triggered

    def _count_memory_entries(self) -> int:
        content = self.memory_manager.read_memory()
        if not content.strip():
            return 0
        return len([line for line in content.splitlines() if line.strip()])

    def compute_decay(self, entry: dict) -> DecayResult:
        """Compute quality decay for a Soul.md experience entry."""
        confidence = entry.get("confidence", 0.0)
        validations = entry.get("validations", 0)
        module = entry.get("module", "")
        exp_type = entry.get("exp_type", "")
        date_str = entry.get("date", "")

        header = f"{date_str} | module:{module} | type:{exp_type}"
        quality = compute_quality_score(confidence, validations)

        age_days = 0
        if date_str:
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d")
                age_days = (datetime.now() - entry_date).days
            except ValueError:
                pass

        if should_deprecate(confidence, validations):
            return DecayResult(
                entry_header=header,
                old_confidence=confidence,
                new_confidence=confidence,
                action="deprecate",
                reason="confidence < 0.3 and 0 validations",
            )

        if should_archive(confidence, validations, age_days):
            return DecayResult(
                entry_header=header,
                old_confidence=confidence,
                new_confidence=confidence,
                action="archive",
                reason="confidence < 0.5 and 0 validations and age > 30 days",
            )

        if quality < 0.5:
            return DecayResult(
                entry_header=header,
                old_confidence=confidence,
                new_confidence=quality,
                action="keep",
                reason=f"low quality score ({quality:.2f}) but not meeting deprecate/archive criteria",
            )

        return DecayResult(
            entry_header=header,
            old_confidence=confidence,
            new_confidence=quality,
            action="keep",
            reason=f"quality score {quality:.2f}",
        )

    def run_decay(self) -> list[DecayResult]:
        """Apply decay computation to all Soul.md entries."""
        soul = self.memory_manager.read_soul()
        entries = soul.get("dynamic", [])
        return [self.compute_decay(entry) for entry in entries]

    def apply_decay(self, results: list[DecayResult], dry_run: bool = False) -> None:
        """Apply decay results: mark entries as deprecated."""
        if dry_run:
            return

        soul = self.memory_manager.read_soul()
        entries = soul.get("dynamic", [])

        deprecate_headers = {
            result.entry_header
            for result in results
            if result.action == "deprecate"
        }

        for entry in entries:
            header = (
                f"{entry.get('date', '')} | module:{entry.get('module', '')} "
                f"| type:{entry.get('exp_type', '')}"
            )
            if header in deprecate_headers:
                entry["deprecated"] = True

        self.memory_manager.write_soul_fixed(soul.get("fixed", ""))
        for entry in entries:
            self.memory_manager.add_experience(
                date=entry.get("date", ""),
                module=entry.get("module", ""),
                exp_type=entry.get("exp_type", ""),
                description=entry.get("description", ""),
                confidence=entry.get("confidence", 0.0),
                abstraction=entry.get("abstraction", ""),
            )

    def archive_deprecated(self, dry_run: bool = False) -> int:
        """Move all deprecated Soul.md entries to Archive.md."""
        soul = self.memory_manager.read_soul()
        entries = soul.get("dynamic", [])

        deprecated = [e for e in entries if e.get("deprecated", False)]
        if not deprecated:
            return 0

        if dry_run:
            return len(deprecated)

        archive_path = self.project_dir / ".agent-flow" / "memory" / "main" / "Archive.md"
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        existing_archive = ""
        if archive_path.is_file():
            existing_archive = archive_path.read_text(encoding="utf-8")

        parts = [existing_archive] if existing_archive else ["# Archived Memories\n\n"]

        for entry in deprecated:
            header = (
                f"## {entry.get('date', '')} | module:{entry.get('module', '')} "
                f"| type:{entry.get('exp_type', '')}"
            )
            source = entry.get("source", "")
            if source:
                header += f" | source:{source}"

            parts.append(header)
            parts.append("")
            parts.append(entry.get("description", ""))
            parts.append(f"confidence: {entry.get('confidence', 0.0)}")
            parts.append(f"validations: {entry.get('validations', 0)}")
            parts.append(f"archived_date: {datetime.now().strftime('%Y-%m-%d')}")
            parts.append(f'archived_reason: "{entry.get("deprecated_reason", "deprecated by organization")}"')
            parts.append("")

        archive_path.write_text("\n".join(parts), encoding="utf-8")

        remaining = [e for e in entries if not e.get("deprecated", False)]
        fixed = soul.get("fixed", "")
        self.memory_manager.write_soul_fixed(fixed)
        for entry in remaining:
            self.memory_manager.add_experience(
                date=entry.get("date", ""),
                module=entry.get("module", ""),
                exp_type=entry.get("exp_type", ""),
                description=entry.get("description", ""),
                confidence=entry.get("confidence", 0.0),
                abstraction=entry.get("abstraction", ""),
            )

        return len(deprecated)

    def promote_high_value(self, dry_run: bool = False) -> list[str]:
        """Memory organization does not promote Skills directly."""
        _ = dry_run
        return []

    def organize_wiki_index(self, dry_run: bool = False) -> int:
        """Reorganize wiki/INDEX.md by removing deprecated references."""
        wiki_index_path = self.project_dir / ".agent-flow" / "wiki" / "INDEX.md"
        ensure_file(wiki_index_path, DEFAULT_WIKI_INDEX)
        if not wiki_index_path.is_file():
            return 0

        content = wiki_index_path.read_text(encoding="utf-8")
        lines = content.splitlines()

        changes = 0
        new_lines = []
        for line in lines:
            if "deprecated" in line.lower():
                changes += 1
                continue
            new_lines.append(line)

        if not dry_run and changes > 0:
            wiki_index_path.write_text("\n".join(new_lines), encoding="utf-8")

        return changes

    def organize_recall_index(self, dry_run: bool = False) -> int:
        """Prune old recall summaries beyond retention period."""
        if dry_run:
            return 0

        recall_manager = RecallManager(self.project_dir)
        return recall_manager.prune_old_summaries(max_age_days=90)

    def run_full_organization(
        self,
        dry_run: bool = False,
        force: bool = False,
        scope: str = "all",
    ) -> OrganizationReport:
        """Execute the full organization pipeline."""
        report = OrganizationReport(timestamp=datetime.now().isoformat())

        if not force:
            triggers = self.check_triggers()
            if not triggers:
                report.decay_results.append(
                    DecayResult(action="skip", reason="No triggers met. Use --force to run anyway.")
                )
                return report

        if scope in ("all", "memory"):
            decay_results = self.run_decay()
            report.memory_entries_scanned = max(self._count_memory_entries(), len(decay_results))
            report.decay_results = decay_results

            for result in decay_results:
                if result.action == "deprecate":
                    report.entries_deprecated += 1
                elif result.action == "archive":
                    report.entries_archived += 1

            if not dry_run:
                self.apply_decay(decay_results)

            archived = self.archive_deprecated(dry_run=dry_run)
            report.entries_archived += archived

            soul = self.memory_manager.read_soul()
            entries = soul.get("dynamic", [])
            compress_groups = should_compress(entries)
            report.entries_compressed = sum(len(group) for group in compress_groups)

        if scope in ("all", "wiki"):
            report.wiki_entries_scanned = self.organize_wiki_index(dry_run=dry_run)

        if scope in ("all", "recall"):
            report.recall_entries_scanned = self.organize_recall_index(dry_run=dry_run)

        if not dry_run:
            self.record_organization_run(report)

        return report

    def record_organization_run(self, report: OrganizationReport) -> None:
        """Write organization report to .agent-flow/logs/organization_log.md."""
        log_dir = self.project_dir / ".agent-flow" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "organization_log.md"

        existing = ""
        if log_path.is_file():
            existing = log_path.read_text(encoding="utf-8")

        parts = [
            f"## [ORGANIZE] {report.timestamp}",
            f"Triggers: {', '.join(self.check_triggers()) or 'forced'}",
            f"Memory entries scanned: {report.memory_entries_scanned}",
            f"Wiki entries scanned: {report.wiki_entries_scanned}",
            f"Recall entries scanned: {report.recall_entries_scanned}",
            f"Deprecated: {report.entries_deprecated}",
            f"Archived: {report.entries_archived}",
            f"Compressed: {report.entries_compressed}",
            "",
        ]

        log_path.write_text(existing + "\n".join(parts), encoding="utf-8")
