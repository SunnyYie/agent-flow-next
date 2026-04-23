"""Cross-session recall — scene summary index and backtracking engine.

Stores compressed session summaries in wiki/recall/ for fast cross-session
search, with the ability to backtrack to original Memory.md / dev_log.md
when more detail is needed.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from agent_flow.core.recall_models import SceneSummary
from agent_flow.core.recall_index_builder import (
    build_recall_entry_markdown,
    build_recall_index_markdown,
    extract_searchable_text,
)
from agent_flow.core.config import ensure_file, DEFAULT_RECALL_INDEX


class RecallManager:
    """Manages scene summaries and cross-session recall queries."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.recall_dir = project_dir / ".agent-flow" / "wiki" / "recall"
        self.dev_workflow_recall_dir = project_dir / ".dev-workflow" / "wiki" / "recall"

    def _active_recall_dir(self) -> Path:
        """Return the recall directory that exists (prefer .agent-flow, fallback .dev-workflow).

        Also ensures INDEX.md exists in the active recall directory (lazy creation).
        """
        if self.recall_dir.is_dir():
            ensure_file(self.recall_dir / "INDEX.md", DEFAULT_RECALL_INDEX)
            return self.recall_dir
        if self.dev_workflow_recall_dir.is_dir():
            ensure_file(self.dev_workflow_recall_dir / "INDEX.md", DEFAULT_RECALL_INDEX)
            return self.dev_workflow_recall_dir
        # Default: create in .agent-flow
        self.recall_dir.mkdir(parents=True, exist_ok=True)
        ensure_file(self.recall_dir / "INDEX.md", DEFAULT_RECALL_INDEX)
        return self.recall_dir

    def save_scene_summary(self, summary: SceneSummary) -> Path:
        """Write summary to wiki/recall/{id}.md with YAML frontmatter.

        Also updates the recall INDEX.md.
        """
        recall_dir = self._active_recall_dir()
        summary_path = recall_dir / f"{summary.id}.md"
        summary_path.write_text(build_recall_entry_markdown(summary), encoding="utf-8")

        # Update index
        self.update_recall_index(summary)
        return summary_path

    def load_recall_index(self) -> list[SceneSummary]:
        """Parse wiki/recall/INDEX.md into a list of SceneSummary models."""
        recall_dir = self._active_recall_dir()
        index_path = recall_dir / "INDEX.md"
        if not index_path.is_file():
            return []

        content = index_path.read_text(encoding="utf-8")
        return self._parse_index_entries(content, recall_dir)

    def update_recall_index(self, summary: SceneSummary) -> None:
        """Rebuild wiki/recall/INDEX.md with all existing summaries."""
        recall_dir = self._active_recall_dir()

        # Load all summaries from files
        summaries = self._load_all_summaries(recall_dir)

        # Add the new summary if not already present
        existing_ids = {s.id for s in summaries}
        if summary.id not in existing_ids:
            summaries.append(summary)

        # Sort by date descending
        summaries.sort(key=lambda s: s.date, reverse=True)

        # Write index
        index_path = recall_dir / "INDEX.md"
        index_path.write_text(build_recall_index_markdown(summaries), encoding="utf-8")

    def search_summaries(self, query: str, limit: int = 10, use_fts5: bool = True) -> list[SceneSummary]:
        """Search summaries by keyword matching across key fields.

        When *use_fts5* is True (default), tries FTS5 full-text search
        via the memory_index module first. Falls back to substring matching
        when the FTS5 index is unavailable.
        """
        if use_fts5:
            fts_results = self._search_via_fts5(query, limit)
            if fts_results is not None:  # None = FTS5 unavailable, [] = no matches
                return fts_results
        return self._search_via_substring(query, limit)

    def _search_via_substring(self, query: str, limit: int) -> list[SceneSummary]:
        """Fallback: pure substring matching across key fields."""
        recall_dir = self._active_recall_dir()
        all_summaries = self._load_all_summaries(recall_dir)

        query_lower = query.lower()
        scored: list[tuple[float, SceneSummary]] = []

        for summary in all_summaries:
            text = extract_searchable_text(summary).lower()
            if query_lower in text:
                # Score by number of keyword matches
                score = text.count(query_lower)
                scored.append((score, summary))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    def _search_via_fts5(self, query: str, limit: int) -> list[SceneSummary] | None:
        """Try FTS5 search via memory_index. Returns None if index unavailable."""
        db_path = self._find_db_path()
        if db_path is None:
            return None

        try:
            from agent_flow.core.memory_index import search_index
            results = search_index(db_path, query, source_type="recall", limit=limit)
        except Exception:
            return None

        if results is None:
            return None

        return self._hydrate_summaries(results, limit)

    def _find_db_path(self) -> str | None:
        """Locate the observations.db for this project."""
        for base in [".agent-flow", ".dev-workflow"]:
            candidate = self.project_dir / base / "observations.db"
            if candidate.is_file():
                return str(candidate)
        return None

    def _hydrate_summaries(self, search_results: list[dict], limit: int) -> list[SceneSummary]:
        """Convert FTS5 search results to SceneSummary objects by loading from files."""
        summaries: list[SceneSummary] = []
        for r in search_results:
            entry_id = r.get("id", "")
            if entry_id.startswith("recall-"):
                stem = entry_id[7:]  # Remove "recall-" prefix
                recall_dir = self._active_recall_dir()
                summary_file = recall_dir / f"{stem}.md"
                summary = self._parse_summary_file(summary_file)
                if summary is not None:
                    summaries.append(summary)
            if len(summaries) >= limit:
                break
        return summaries

    def backtrack_to_source(self, summary: SceneSummary) -> str:
        """Given a summary, read and return the original Memory.md or dev_log.md content.

        Returns empty string if source no longer exists.
        """
        if not summary.source_log:
            return ""

        source_path = self.project_dir / summary.source_log
        if not source_path.is_file():
            return ""

        return source_path.read_text(encoding="utf-8")

    def get_recent_summaries(self, n: int = 5) -> list[SceneSummary]:
        """Return the N most recent scene summaries for quick context loading."""
        recall_dir = self._active_recall_dir()
        all_summaries = self._load_all_summaries(recall_dir)

        # Sort by date descending
        all_summaries.sort(key=lambda s: s.date, reverse=True)
        return all_summaries[:n]

    def prune_old_summaries(self, max_age_days: int = 90) -> int:
        """Remove scene summaries older than max_age_days.

        Returns count of pruned entries.
        """
        recall_dir = self._active_recall_dir()
        now = datetime.now()
        pruned = 0

        for summary_file in recall_dir.glob("*.md"):
            if summary_file.name == "INDEX.md":
                continue

            summary = self._parse_summary_file(summary_file)
            if summary is None:
                continue

            try:
                summary_date = datetime.strptime(summary.date, "%Y-%m-%d")
                if (now - summary_date).days > max_age_days:
                    summary_file.unlink()
                    pruned += 1
            except ValueError:
                continue

        # Rebuild index after pruning
        if pruned > 0:
            summaries = self._load_all_summaries(recall_dir)
            index_path = recall_dir / "INDEX.md"
            index_path.write_text(build_recall_index_markdown(summaries), encoding="utf-8")

        return pruned

    # -- Internal helpers -------------------------------------------------------

    def _load_all_summaries(self, recall_dir: Path) -> list[SceneSummary]:
        """Load all scene summary files from the recall directory."""
        summaries: list[SceneSummary] = []
        if not recall_dir.is_dir():
            return summaries

        for md_file in recall_dir.glob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            summary = self._parse_summary_file(md_file)
            if summary is not None:
                summaries.append(summary)

        return summaries

    @staticmethod
    def _parse_summary_file(path: Path) -> Optional[SceneSummary]:
        """Parse a scene summary Markdown file with YAML frontmatter."""
        try:
            content = path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return None

            end = content.find("---", 3)
            if end == -1:
                return None

            frontmatter_str = content[3:end]
            data = yaml.safe_load(frontmatter_str)
            if not isinstance(data, dict):
                return None

            # Map YAML keys to SceneSummary fields
            return SceneSummary(
                id=data.get("id", path.stem),
                date=data.get("date", ""),
                task_description=data.get("task", ""),
                phases_completed=data.get("phases", []),
                key_decisions=data.get("decisions", []),
                experiences_extracted=data.get("experiences", []),
                skills_created=data.get("skills_created", []),
                wiki_entries_created=data.get("wiki_created", []),
                errors_encountered=data.get("errors", []),
                outcome=data.get("outcome", ""),
                source_log=data.get("source_log", ""),
                confidence=float(data.get("confidence", 0.0)),
            )
        except Exception:
            return None

    @staticmethod
    def _parse_index_entries(content: str, recall_dir: Path) -> list[SceneSummary]:
        """Parse INDEX.md to extract summary references.

        The INDEX.md contains a table with Date, Task, Outcome, ID columns.
        We load the actual summary files referenced in the table.
        """
        summaries: list[SceneSummary] = []

        # Look for markdown links to summary files
        for match in re.finditer(r"\[([^\]]+)\]\(([^)]+\.md)\)", content):
            link_path = match.group(2)
            summary_file = recall_dir / link_path
            if summary_file.is_file():
                summary = RecallManager._parse_summary_file(summary_file)
                if summary is not None:
                    summaries.append(summary)

        return summaries
