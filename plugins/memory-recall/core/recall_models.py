"""Recall data models — SceneSummary and related types.

Separated from recall.py to avoid circular imports with recall_index_builder.py.
"""

from pydantic import BaseModel, Field


class SceneSummary(BaseModel):
    """A compressed scene summary stored in wiki/recall/."""

    id: str = ""  # "{date}-{slug}"
    date: str = ""  # ISO date
    task_description: str = ""
    phases_completed: list[str] = Field(default_factory=list)
    key_decisions: list[str] = Field(default_factory=list)
    experiences_extracted: list[str] = Field(default_factory=list)
    skills_created: list[str] = Field(default_factory=list)
    wiki_entries_created: list[str] = Field(default_factory=list)
    errors_encountered: list[str] = Field(default_factory=list)
    outcome: str = ""  # "success" | "partial" | "failed"
    source_log: str = ""  # Relative path to original Memory.md or dev_log.md
    confidence: float = 0.0
