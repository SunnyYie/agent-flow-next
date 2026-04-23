"""User behavior observer — rule-based inference from session summaries.

Processes SceneSummary data to infer user preferences, work style,
autonomy level, and behavior patterns. All rules are deterministic
(no LLM calls).
"""

from datetime import date

from agent_flow.core.recall_models import SceneSummary
from agent_flow.core.user_model import (
    UserProfile,
    TechStackPreference,
    WorkStylePreference,
    AutonomyLevel,
    BehaviorPattern,
)


class UserObserver:
    """Rule-based engine that processes session summaries into user observations."""

    def process_summary(self, summary: SceneSummary, profile: UserProfile) -> UserProfile:
        """Apply all observation rules to a session summary, updating the profile.

        Returns the updated profile.
        """
        profile = self._infer_tech_preferences(summary, profile)
        profile = self._infer_work_style(summary, profile)
        profile = self._infer_autonomy(summary, profile)
        profile = self._detect_behavior_patterns(summary, profile)
        return profile

    def _infer_tech_preferences(self, summary: SceneSummary, profile: UserProfile) -> UserProfile:
        """Update tech stack preferences based on tools/skills used in session."""
        ts = profile.tech_stack

        # Track skill usage as tool preferences
        for skill_name in summary.skills_created:
            skill_lower = skill_name.lower()
            if skill_lower not in [t.lower() for t in ts.preferred_tools]:
                ts.preferred_tools.append(skill_name)

        # Extract tool mentions from experiences
        for exp in summary.experiences_extracted:
            # Look for tool installation patterns
            for keyword in ["pip install", "npm install", "brew install", "cargo install", "uv "]:
                if keyword in exp.lower():
                    # Extract tool name after install command
                    parts = exp.lower().split(keyword)
                    if len(parts) > 1:
                        tool_name = parts[1].strip().split()[0] if parts[1].strip() else ""
                        if tool_name and tool_name not in [t.lower() for t in ts.preferred_tools]:
                            ts.preferred_tools.append(tool_name)

        # Track frameworks from decisions
        for decision in summary.key_decisions:
            known_frameworks = [
                "react", "vue", "svelte", "angular", "nextjs", "nuxt",
                "fastapi", "django", "flask", "express", "koa", "nestjs",
                "langchain", "langgraph",
            ]
            decision_lower = decision.lower()
            for fw in known_frameworks:
                if fw in decision_lower and fw not in [f.lower() for f in ts.preferred_frameworks]:
                    ts.preferred_frameworks.append(fw)

        profile.tech_stack = ts
        return profile

    def _infer_work_style(self, summary: SceneSummary, profile: UserProfile) -> UserProfile:
        """Update work style preferences based on session patterns."""
        ws = profile.work_style

        # If session had VERIFY phase, user likely prefers standard+ verification
        if "VERIFY" in summary.phases_completed:
            if ws.preferred_verification_level == "minimal":
                # User accepted verification this time, bump up
                ws.preferred_verification_level = "standard"

        # If session had many errors, suggest thorough verification
        if len(summary.errors_encountered) >= 3:
            ws.preferred_verification_level = "thorough"

        # If session completed all phases successfully, it's a positive signal
        if summary.outcome == "success" and len(summary.phases_completed) >= 4:
            # Over time, if user consistently succeeds, they may prefer less confirmation
            pass  # Don't auto-change, just track

        profile.work_style = ws
        return profile

    def _infer_autonomy(self, summary: SceneSummary, profile: UserProfile) -> UserProfile:
        """Update autonomy level based on confirmation patterns.

        Note: This is conservative. We only increase autonomy if the user
        has a consistent track record of success without intervention.
        """
        al = profile.autonomy

        # Track success rate implicitly
        if summary.outcome == "success" and profile.observation_count >= 5:
            # After enough successful observations, consider bumping autonomy
            if al.level < 3 and profile.observation_count % 10 == 0:
                # Only suggest, don't auto-change
                pass

        if summary.outcome == "failed" and al.level >= 4:
            # High autonomy + failure = suggest reducing
            pass  # Don't auto-reduce, just track

        profile.autonomy = al
        return profile

    def _detect_behavior_patterns(self, summary: SceneSummary, profile: UserProfile) -> UserProfile:
        """Detect and record behavior patterns from the session."""
        today = date.today().isoformat()

        # Pattern: "starts with {phase}" pattern
        if summary.phases_completed:
            first_phase = summary.phases_completed[0]
            pattern_desc = f"always starts with {first_phase}"
            profile = self._upsert_pattern(profile, pattern_desc, summary.id, today)

        # Pattern: "uses {skill}" pattern
        for skill in summary.skills_created:
            pattern_desc = f"frequently uses {skill}"
            profile = self._upsert_pattern(profile, pattern_desc, summary.id, today)

        # Pattern: "encounters errors in {module}" pattern
        for exp in summary.experiences_extracted:
            if "module:" in exp:
                module = exp.split("module:")[1].split("|")[0].strip()
                if exp.split("type:")[1].split("|")[0].strip() if "type:" in exp else "" == "pitfall":
                    pattern_desc = f"often encounters pitfalls in {module}"
                    profile = self._upsert_pattern(profile, pattern_desc, summary.id, today)

        # Pattern: "prefers parallel execution" from task description
        if "parallel" in summary.task_description.lower():
            profile = self._upsert_pattern(profile, "prefers parallel execution", summary.id, today)

        return profile

    @staticmethod
    def _upsert_pattern(
        profile: UserProfile, pattern_desc: str, session_id: str, today: str
    ) -> UserProfile:
        """Insert or update a behavior pattern in the profile."""
        # Check if pattern already exists
        for bp in profile.behavior_patterns:
            if bp.pattern == pattern_desc:
                bp.frequency += 1
                bp.last_seen = today
                bp.confidence = min(1.0, bp.confidence + 0.1)
                if session_id not in bp.source_sessions:
                    bp.source_sessions.append(session_id)
                return profile

        # Create new pattern
        profile.behavior_patterns.append(BehaviorPattern(
            pattern=pattern_desc,
            frequency=1,
            first_seen=today,
            last_seen=today,
            confidence=0.3,
            source_sessions=[session_id],
        ))
        return profile

    def detect_tool_preferences(self, summary: SceneSummary) -> list[tuple[str, str]]:
        """Detect tool usage patterns. Returns [(tool_name, preference_direction)]."""
        preferences: list[tuple[str, str]] = []

        for skill in summary.skills_created:
            preferences.append((skill, "positive"))

        # Check for avoidance signals in errors
        for error in summary.errors_encountered:
            error_lower = error.lower()
            if any(word in error_lower for word in ["uninstalled", "refused", "avoid", "rejected"]):
                # Very basic detection — real system would need NLP
                preferences.append(("unknown", "negative"))

        return preferences

    def detect_verification_preferences(self, summary: SceneSummary) -> dict:
        """Detect whether user prefers thorough or minimal verification."""
        result: dict = {"level": "standard"}

        if "VERIFY" not in summary.phases_completed:
            result["level"] = "minimal"
        elif len(summary.errors_encountered) >= 3:
            result["level"] = "thorough"

        return result

    def detect_session_patterns(self, summary: SceneSummary) -> list[str]:
        """Detect recurring session patterns."""
        patterns: list[str] = []

        if summary.phases_completed:
            patterns.append(f"starts_with_{summary.phases_completed[0].lower()}")

        if summary.outcome == "success" and len(summary.phases_completed) >= 5:
            patterns.append("completes_full_cycle")

        if summary.skills_created:
            patterns.append(f"creates_skills")

        return patterns
