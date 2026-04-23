"""Frozen memory snapshot — hermes frozen snapshot concept.

Session-start load into system prompt prefix, session writes only update
disk (not the prompt), keeping prefix cache stable across the session.
"""

import hashlib
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agent_flow.core.config import project_skills_dirs
from agent_flow.core.memory import MemoryManager


class FrozenMemorySnapshot(BaseModel):
    """A frozen snapshot of memory loaded at session start."""

    memory_content: str = ""
    soul_fixed: str = ""
    user_profile: str = ""
    relevant_skills: list[str] = Field(default_factory=list)
    relevant_experiences: list[dict] = Field(default_factory=list)
    snapshot_timestamp: str = ""
    checksum: str = ""  # For prefix cache stability detection


class FrozenMemoryManager:
    """Hermes frozen snapshot mode.

    Key invariant: once loaded into the system prompt prefix, the snapshot
    is never mutated during the session. Writes go to disk for the next session.

    This preserves Anthropic prefix cache stability — the frozen content
    stays identical across all API calls in a session.
    """

    def __init__(self, project_dir: Path, agent_name: str = "main") -> None:
        self.project_dir = project_dir
        self.agent_name = agent_name
        self.memory_manager = MemoryManager(project_dir, agent_name)

    def load_snapshot(self) -> FrozenMemorySnapshot:
        """Load a frozen snapshot from current memory state.

        Captures: Memory.md, Soul.md fixed section, relevant skills,
        and high-confidence experiences. Computes a checksum for
        cache stability detection.
        """
        now = datetime.now().isoformat()

        # Read working memory
        memory_content = self.memory_manager.read_memory()

        # Read Soul fixed section
        soul = self.memory_manager.read_soul()
        soul_fixed = soul.get("fixed", "")

        # Read high-confidence experiences (top 5)
        dynamic = soul.get("dynamic", [])
        sorted_experiences = sorted(
            dynamic, key=lambda e: e.get("confidence", 0.0), reverse=True
        )
        relevant_experiences = sorted_experiences[:5]

        # Load relevant skills from project knowledge roots, then global fallback.
        relevant_skills = self._load_skill_triggers()

        # Load user profile
        user_profile = self._load_user_profile()

        # Compute checksum of all content for cache stability detection
        checksum = self._compute_checksum(
            memory_content, soul_fixed, relevant_skills, relevant_experiences, user_profile
        )

        return FrozenMemorySnapshot(
            memory_content=memory_content,
            soul_fixed=soul_fixed,
            user_profile=user_profile,
            relevant_skills=relevant_skills,
            relevant_experiences=relevant_experiences,
            snapshot_timestamp=now,
            checksum=checksum,
        )

    def is_snapshot_fresh(self, snapshot: FrozenMemorySnapshot) -> bool:
        """Check if the on-disk content matches the snapshot.

        Returns True if the snapshot is still fresh (no disk changes since load).
        Returns False if disk content has changed.
        """
        current = self.load_snapshot()
        return current.checksum == snapshot.checksum

    def format_for_system_prompt(self, snapshot: FrozenMemorySnapshot) -> str:
        """Format the frozen snapshot as a system prompt section.

        The output is deterministic for identical snapshots — critical for
        prefix cache stability.
        """
        parts: list[str] = []

        if snapshot.soul_fixed:
            parts.append("<agent_identity>")
            parts.append(snapshot.soul_fixed.strip())
            parts.append("</agent_identity>")

        if snapshot.user_profile:
            parts.append("<user_profile>")
            parts.append(snapshot.user_profile.strip())
            parts.append("</user_profile>")

        if snapshot.relevant_experiences:
            parts.append("<relevant_experiences>")
            for exp in snapshot.relevant_experiences:
                module = exp.get("module", "")
                exp_type = exp.get("exp_type", "")
                description = exp.get("description", "")
                confidence = exp.get("confidence", 0.0)
                parts.append(f"- [{module}/{exp_type}] ({confidence:.1f}) {description[:200]}")
            parts.append("</relevant_experiences>")

        if snapshot.relevant_skills:
            parts.append("<available_skills>")
            for skill_name in snapshot.relevant_skills:
                parts.append(f"- {skill_name}")
            parts.append("</available_skills>")

        if snapshot.memory_content:
            parts.append("<working_memory>")
            parts.append(snapshot.memory_content.strip())
            parts.append("</working_memory>")

        return "\n".join(parts)

    def write_memory_disk_only(self, entry: str) -> None:
        """Write to Memory.md on disk without updating any snapshot object.

        This is the key hermes pattern: session writes go to disk for
        the next session, but the current session's prompt prefix stays
        frozen (unchanged) for cache stability.
        """
        self.memory_manager.append_memory(entry)

    # -- Internal helpers -----------------------------------------------------

    def _load_skill_triggers(self) -> list[str]:
        """Load skill names from project skill roots, then global skills."""
        skills: list[str] = []
        for skills_dir in project_skills_dirs(self.project_dir, include_legacy=True):
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                handler = skill_dir / "handler.md"
                if handler.is_file() and skill_dir.name not in skills:
                    skills.append(skill_dir.name)

        # Also check global skills
        global_skills_dir = Path.home() / ".agent-flow" / "skills"
        if global_skills_dir.is_dir():
            for skill_dir in sorted(global_skills_dir.iterdir()):
                if skill_dir.is_dir() and skill_dir.name not in skills:
                    skills.append(skill_dir.name)

        return skills[:20]  # Cap to avoid oversized prompts

    def _load_user_profile(self) -> str:
        """Load user profile from ~/.agent-flow/user/profile.md."""
        profile_path = Path.home() / ".agent-flow" / "user" / "profile.md"
        if not profile_path.is_file():
            return ""
        try:
            return profile_path.read_text(encoding="utf-8")
        except Exception:
            return ""

    @staticmethod
    def _compute_checksum(
        memory_content: str,
        soul_fixed: str,
        skills: list[str],
        experiences: list[dict],
        user_profile: str,
    ) -> str:
        """Compute a deterministic checksum of all snapshot content."""
        hasher = hashlib.sha256()
        hasher.update(memory_content.encode("utf-8"))
        hasher.update(soul_fixed.encode("utf-8"))
        for skill in skills:
            hasher.update(skill.encode("utf-8"))
        for exp in experiences:
            hasher.update(exp.get("description", "").encode("utf-8"))
            hasher.update(str(exp.get("confidence", 0.0)).encode("utf-8"))
        hasher.update(user_profile.encode("utf-8"))
        return hasher.hexdigest()[:16]
