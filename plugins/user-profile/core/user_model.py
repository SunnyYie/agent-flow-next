"""Active user modeling — build and maintain dynamic user profile across sessions.

Stores user preferences, tech stack, autonomy level, and behavior patterns
in ~/.agent-flow/user/profile.md. Automatically inferred from session summaries.
"""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agent_flow.core.recall_models import SceneSummary


class TechStackPreference(BaseModel):
    """User's observed technology preferences."""

    primary_language: str = ""
    preferred_frameworks: list[str] = Field(default_factory=list)
    preferred_tools: list[str] = Field(default_factory=list)
    avoidance_list: list[str] = Field(default_factory=list)
    package_manager_preference: str = ""


class WorkStylePreference(BaseModel):
    """User's observed work style patterns."""

    preferred_verification_level: str = "standard"  # minimal|standard|thorough
    preferred_communication_style: str = "concise"  # concise|detailed|annotated
    preferred_task_decomposition: str = "medium"  # fine|medium|coarse
    prefers_parallel: bool = False
    prefers_manual_confirmation: bool = True


class AutonomyLevel(BaseModel):
    """User's current autonomy delegation level."""

    level: int = 1  # 1-5 scale
    description: str = "confirm-most"  # auto-execute|confirm-major|confirm-most|confirm-all|manual-only
    auto_install_tools: bool = False
    auto_commit: bool = False
    auto_push: bool = False
    auto_test: bool = True


class BehaviorPattern(BaseModel):
    """A single observed behavior pattern."""

    pattern: str
    frequency: int = 1
    first_seen: str = ""
    last_seen: str = ""
    confidence: float = 0.5
    source_sessions: list[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    """Complete user profile, stored in ~/.agent-flow/user/profile.md."""

    user_id: str = "default"
    created: str = ""
    last_updated: str = ""
    tech_stack: TechStackPreference = Field(default_factory=TechStackPreference)
    work_style: WorkStylePreference = Field(default_factory=WorkStylePreference)
    autonomy: AutonomyLevel = Field(default_factory=AutonomyLevel)
    behavior_patterns: list[BehaviorPattern] = Field(default_factory=list)
    observation_count: int = 0


# Autonomy level descriptions
AUTONOMY_DESCRIPTIONS = {
    1: "confirm-most",
    2: "confirm-all",
    3: "confirm-major",
    4: "confirm-minor",
    5: "auto-execute",
}

AUTONOMY_FLAGS = {
    1: {"auto_install_tools": False, "auto_commit": False, "auto_push": False, "auto_test": True},
    2: {"auto_install_tools": False, "auto_commit": False, "auto_push": False, "auto_test": True},
    3: {"auto_install_tools": True, "auto_commit": False, "auto_push": False, "auto_test": True},
    4: {"auto_install_tools": True, "auto_commit": True, "auto_push": False, "auto_test": True},
    5: {"auto_install_tools": True, "auto_commit": True, "auto_push": True, "auto_test": True},
}


class UserModelManager:
    """Manages user profile storage and behavioral observation inference."""

    def __init__(self) -> None:
        self.user_dir = Path.home() / ".agent-flow" / "user"
        self.profile_path = self.user_dir / "profile.md"
        self.observations_path = self.user_dir / "observations.md"

    def load_profile(self) -> UserProfile:
        """Load user profile from ~/.agent-flow/user/profile.md.

        Parses YAML frontmatter from the Markdown file.
        Returns a default profile if file doesn't exist.
        """
        if not self.profile_path.is_file():
            return UserProfile()

        try:
            content = self.profile_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                return UserProfile()

            end = content.find("---", 3)
            if end == -1:
                return UserProfile()

            frontmatter_str = content[3:end]
            data = yaml.safe_load(frontmatter_str)
            if not isinstance(data, dict):
                return UserProfile()

            return self._dict_to_profile(data)
        except Exception:
            return UserProfile()

    def save_profile(self, profile: UserProfile) -> None:
        """Write user profile to ~/.agent-flow/user/profile.md."""
        self.user_dir.mkdir(parents=True, exist_ok=True)
        md = self._profile_to_markdown(profile)
        self.profile_path.write_text(md, encoding="utf-8")

    def observe_session(self, summary: SceneSummary) -> UserProfile:
        """Infer behavioral observations from a completed session's recall summary.

        Updates the user profile with new observations.
        Returns the updated profile.
        """
        from agent_flow.core.user_observer import UserObserver

        profile = self.load_profile()

        # Update observation count
        profile.observation_count += 1
        profile.last_updated = date.today().isoformat()
        if not profile.created:
            profile.created = date.today().isoformat()

        # Apply observation rules
        observer = UserObserver()
        profile = observer.process_summary(summary, profile)

        self.save_profile(profile)

        # Log observation
        self._log_observation(summary, profile)

        return profile

    def set_autonomy(self, level: int) -> UserProfile:
        """Set the autonomy level (1-5) and update associated flags."""
        level = max(1, min(5, level))
        profile = self.load_profile()
        profile.autonomy.level = level
        profile.autonomy.description = AUTONOMY_DESCRIPTIONS.get(level, "confirm-most")
        flags = AUTONOMY_FLAGS.get(level, AUTONOMY_FLAGS[1])
        profile.autonomy.auto_install_tools = flags["auto_install_tools"]
        profile.autonomy.auto_commit = flags["auto_commit"]
        profile.autonomy.auto_push = flags["auto_push"]
        profile.autonomy.auto_test = flags["auto_test"]
        profile.last_updated = date.today().isoformat()
        self.save_profile(profile)
        return profile

    def add_avoidance(self, tool_or_framework: str) -> UserProfile:
        """Add a tool or framework to the avoidance list."""
        profile = self.load_profile()
        if tool_or_framework not in profile.tech_stack.avoidance_list:
            profile.tech_stack.avoidance_list.append(tool_or_framework)
            profile.last_updated = date.today().isoformat()
            self.save_profile(profile)
        return profile

    def get_task_allocation_hints(self) -> dict:
        """Return hints for multi-agent task allocation based on user profile."""
        profile = self.load_profile()
        return {
            "prefers_parallel": profile.work_style.prefers_parallel,
            "verification_level": profile.work_style.preferred_verification_level,
            "autonomy_level": profile.autonomy.level,
            "avoidance_list": profile.tech_stack.avoidance_list,
            "preferred_tools": profile.tech_stack.preferred_tools,
        }

    def get_execution_strategy(self) -> dict:
        """Return execution strategy parameters based on user model.

        Affects THINK phase decisions (serial vs parallel, verification depth).
        """
        profile = self.load_profile()
        return {
            "execution_mode": "parallel" if profile.work_style.prefers_parallel else "serial",
            "verification_depth": profile.work_style.preferred_verification_level,
            "confirmation_threshold": "low" if profile.autonomy.level >= 4 else "high",
            "auto_test": profile.autonomy.auto_test,
            "auto_install": profile.autonomy.auto_install_tools,
        }

    # -- Internal helpers -------------------------------------------------------

    @staticmethod
    def _dict_to_profile(data: dict) -> UserProfile:
        """Convert a dict (from YAML) to a UserProfile model."""
        tech_data = data.get("tech_stack", {})
        work_data = data.get("work_style", {})
        autonomy_data = data.get("autonomy", {})
        patterns_data = data.get("behavior_patterns", [])

        return UserProfile(
            user_id=data.get("user_id", "default"),
            created=data.get("created", ""),
            last_updated=data.get("last_updated", ""),
            tech_stack=TechStackPreference(**{
                k: v for k, v in tech_data.items()
                if k in TechStackPreference.model_fields
            }) if isinstance(tech_data, dict) else TechStackPreference(),
            work_style=WorkStylePreference(**{
                k: v for k, v in work_data.items()
                if k in WorkStylePreference.model_fields
            }) if isinstance(work_data, dict) else WorkStylePreference(),
            autonomy=AutonomyLevel(**{
                k: v for k, v in autonomy_data.items()
                if k in AutonomyLevel.model_fields
            }) if isinstance(autonomy_data, dict) else AutonomyLevel(),
            behavior_patterns=[
                BehaviorPattern(**{
                    k: v for k, v in p.items()
                    if k in BehaviorPattern.model_fields
                }) for p in patterns_data if isinstance(p, dict)
            ],
            observation_count=data.get("observation_count", 0),
        )

    @staticmethod
    def _profile_to_markdown(profile: UserProfile) -> str:
        """Render a UserProfile as Markdown with YAML frontmatter."""
        data = {
            "user_id": profile.user_id,
            "created": profile.created,
            "last_updated": profile.last_updated,
            "observation_count": profile.observation_count,
            "tech_stack": profile.tech_stack.model_dump(),
            "work_style": profile.work_style.model_dump(),
            "autonomy": profile.autonomy.model_dump(),
            "behavior_patterns": [p.model_dump() for p in profile.behavior_patterns],
        }

        fm_str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

        # Build readable body
        parts = [
            "# User Profile",
            "",
            "## Tech Stack Preferences",
        ]
        ts = profile.tech_stack
        parts.append(f"- primary_language: {ts.primary_language or '(not set)'}")
        parts.append(f"- preferred_frameworks: {ts.preferred_frameworks or '[]'}")
        parts.append(f"- preferred_tools: {ts.preferred_tools or '[]'}")
        parts.append(f"- avoidance_list: {ts.avoidance_list or '[]'}")
        parts.append(f"- package_manager_preference: {ts.package_manager_preference or '(not set)'}")
        parts.append("")

        parts.append("## Work Style")
        ws = profile.work_style
        parts.append(f"- preferred_verification_level: {ws.preferred_verification_level}")
        parts.append(f"- preferred_communication_style: {ws.preferred_communication_style}")
        parts.append(f"- preferred_task_decomposition: {ws.preferred_task_decomposition}")
        parts.append(f"- prefers_parallel: {ws.prefers_parallel}")
        parts.append(f"- prefers_manual_confirmation: {ws.prefers_manual_confirmation}")
        parts.append("")

        parts.append("## Autonomy Level")
        al = profile.autonomy
        parts.append(f"- level: {al.level}")
        parts.append(f"- description: {al.description}")
        parts.append(f"- auto_install_tools: {al.auto_install_tools}")
        parts.append(f"- auto_commit: {al.auto_commit}")
        parts.append(f"- auto_push: {al.auto_push}")
        parts.append(f"- auto_test: {al.auto_test}")
        parts.append("")

        parts.append("## Behavior Patterns")
        if profile.behavior_patterns:
            parts.append("| Pattern | Frequency | First Seen | Last Seen | Confidence |")
            parts.append("|---------|-----------|------------|-----------|------------|")
            for bp in profile.behavior_patterns:
                parts.append(f"| {bp.pattern} | {bp.frequency} | {bp.first_seen} | {bp.last_seen} | {bp.confidence} |")
        else:
            parts.append("(none yet)")
        parts.append("")

        return f"---\n{fm_str}---\n\n" + "\n".join(parts)

    def _log_observation(self, summary: SceneSummary, profile: UserProfile) -> None:
        """Append observation details to observations.md."""
        self.user_dir.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        lines = [
            f"## {today} | Session: {summary.id}",
            f"- Observed: task '{summary.task_description[:50]}'",
        ]

        if summary.skills_created:
            lines.append(f"- Observed: used skills {summary.skills_created} (tool preference signal)")
        if summary.outcome == "failed":
            lines.append("- Observed: task failed (potential frustration signal)")
        if summary.errors_encountered:
            lines.append(f"- Observed: encountered {len(summary.errors_encountered)} errors")

        lines.append("")

        # Append to existing observations
        existing = ""
        if self.observations_path.is_file():
            existing = self.observations_path.read_text(encoding="utf-8")

        self.observations_path.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")
