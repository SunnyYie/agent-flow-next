"""AgentTeam — Agent Team configuration model and initialization logic.

Manages the lifecycle of agent team configurations based on task complexity:
  - Simple (0-3): solo mode — no team, main agent works alone
  - Medium (4-6): search-only mode — main + searcher for knowledge retrieval
  - Complex (7-10): full-team mode — main + searcher + executor + verifier

The team config is written to `.agent-flow/state/agent-team-config.yaml` and
injected into the startup context for the main agent to reference.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


# ── Constants ──────────────────────────────────────────────────

AGENT_TEAM_CONFIG_FILENAME = "agent-team-config.yaml"

TEAM_MODE_SOLO = "solo"
TEAM_MODE_SEARCH_ONLY = "search-only"
TEAM_MODE_FULL_TEAM = "full-team"

COMPLEXITY_TEAM_MAP: dict[str, str] = {
    "simple": TEAM_MODE_SOLO,
    "medium": TEAM_MODE_SEARCH_ONLY,
    "complex": TEAM_MODE_FULL_TEAM,
}

DISPATCH_PHASE_THINK = "THINK"
DISPATCH_PHASE_EXECUTE = "EXECUTE"
DISPATCH_PHASE_VERIFY = "VERIFY"


# ── Models ─────────────────────────────────────────────────────


class AgentTeamMember(BaseModel):
    """A single agent in the team."""

    role: str = Field(description="Functional role: coordinator, knowledge-retrieval, implementation, verification")
    activated: bool = Field(default=False, description="Whether this agent is active for the current task")
    responsibilities: list[str] = Field(default_factory=list)
    dispatch_phase: str = Field(default="", description="When to dispatch this agent (THINK/EXECUTE/VERIFY)")


class ExecutorPoolConfig(BaseModel):
    """Configuration for a pool of parallel executors."""

    max_parallel: int = Field(default=1, ge=1, le=3, description="Max parallel executors (1-3)")
    executors: dict[str, AgentTeamMember] = Field(default_factory=dict, description="Named executor instances")
    context_mode: str = Field(
        default="shared+independent",
        description="shared | shared+independent | independent",
    )


class HandoffProtocol(BaseModel):
    """How agents pass results between each other."""

    format: str = Field(default="l1-l2-l3")
    l1: str = "1-line summary in flow-context.yaml"
    l2: str = "structured summary ≤20 lines in .agent-flow/artifacts/"
    l3: str = "full result, accessed only via sub-agent analyst"


class AgentTeamConfig(BaseModel):
    """Full team configuration for the current task."""

    schema_version: int = Field(default=1)
    task_complexity: str = Field(description="simple | medium | complex")
    team_mode: str = Field(description="solo | search-only | full-team")
    activated_at: str = Field(default="")
    team: dict[str, AgentTeamMember] = Field(default_factory=dict)
    executor_pool: ExecutorPoolConfig | None = Field(
        default=None, description="Parallel executor pool (None=single executor)"
    )
    handoff_protocol: HandoffProtocol = Field(default_factory=HandoffProtocol)

    # ── Factory ────────────────────────────────────────────────

    @classmethod
    def from_complexity(cls, level: str) -> AgentTeamConfig:
        """Create team config from complexity level."""
        level = level.lower().strip()
        mode = COMPLEXITY_TEAM_MAP.get(level, TEAM_MODE_SOLO)
        team = _build_team(mode)
        return cls(
            task_complexity=level,
            team_mode=mode,
            activated_at=datetime.now().isoformat(timespec="seconds"),
            team=team,
        )

    @classmethod
    def from_complexity_with_parallelism(cls, level: str, max_parallel: int = 1) -> AgentTeamConfig:
        """Create team config with explicit parallel executor count."""
        config = cls.from_complexity(level)
        if config.is_full_team() and max_parallel > 1:
            capped = min(max_parallel, 3)
            config.executor_pool = ExecutorPoolConfig(
                max_parallel=capped,
                executors={
                    f"executor-{i+1}": AgentTeamMember(
                        role="implementation",
                        activated=True,
                        responsibilities=[
                            "Execute assigned task subset",
                            "Write incremental artifacts",
                            "Respect file ownership boundaries",
                        ],
                        dispatch_phase=DISPATCH_PHASE_EXECUTE,
                    )
                    for i in range(capped)
                },
            )
        return config

    # ── Serialization ──────────────────────────────────────────

    def to_yaml(self) -> str:
        return yaml.dump(self.model_dump(), default_flow_style=False, allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> AgentTeamConfig:
        data = yaml.safe_load(text)
        return cls.model_validate(data)

    # ── File I/O ───────────────────────────────────────────────

    def write(self, project_dir: str | Path) -> Path:
        """Write config to .agent-flow/state/agent-team-config.yaml."""
        state_dir = Path(project_dir) / ".agent-flow" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        path = state_dir / AGENT_TEAM_CONFIG_FILENAME
        path.write_text(self.to_yaml(), encoding="utf-8")
        return path

    @classmethod
    def read(cls, project_dir: str | Path) -> AgentTeamConfig | None:
        """Read config from disk, returns None if not found."""
        path = Path(project_dir) / ".agent-flow" / "state" / AGENT_TEAM_CONFIG_FILENAME
        if not path.exists():
            return None
        return cls.from_yaml(path.read_text(encoding="utf-8"))

    @classmethod
    def remove(cls, project_dir: str | Path) -> None:
        """Remove config file (session cleanup)."""
        path = Path(project_dir) / ".agent-flow" / "state" / AGENT_TEAM_CONFIG_FILENAME
        if path.exists():
            path.unlink()

    # ── Helpers ────────────────────────────────────────────────

    def activated_agents(self) -> list[str]:
        """Return list of activated agent names."""
        return [name for name, member in self.team.items() if member.activated]

    def is_solo(self) -> bool:
        return self.team_mode == TEAM_MODE_SOLO

    def is_search_only(self) -> bool:
        return self.team_mode == TEAM_MODE_SEARCH_ONLY

    def is_full_team(self) -> bool:
        return self.team_mode == TEAM_MODE_FULL_TEAM

    def is_parallel_execution(self) -> bool:
        """Whether this team uses parallel executors."""
        return self.executor_pool is not None and self.executor_pool.max_parallel > 1

    def parallel_executor_count(self) -> int:
        """Number of parallel executors, or 1 if single."""
        if self.executor_pool is None:
            return 1
        return self.executor_pool.max_parallel

    def get_executor_names(self) -> list[str]:
        """List of executor instance names."""
        if self.executor_pool is None:
            return ["executor"]
        return list(self.executor_pool.executors.keys()) or [
            f"executor-{i+1}" for i in range(self.executor_pool.max_parallel)
        ]

    def injection_summary(self) -> str:
        """One-line summary for hook injection into startup context."""
        if self.is_solo():
            return ""

        agents = self.activated_agents()
        schedule = ", ".join(
            f"{name}→{self.team[name].dispatch_phase}"
            for name in agents
            if self.team[name].dispatch_phase
        )

        parts = [
            f"team_mode: {self.team_mode}",
            f"activated: {agents}",
        ]
        if schedule:
            parts.append(f"schedule: {schedule}")

        if self.is_full_team():
            parts.append("protocol: L1/L2/L3 compression")
            if self.is_parallel_execution():
                parts.append(f"parallel: {self.parallel_executor_count()} executors")
        else:
            parts.append("handoff: .agent-flow/artifacts/search-{id}-results.md")

        return " | ".join(parts)


# ── Team builder ───────────────────────────────────────────────


def _build_team(mode: str) -> dict[str, AgentTeamMember]:
    """Build team members based on mode."""
    main = AgentTeamMember(
        role="coordinator",
        activated=True,
        responsibilities=[
            "Coordinate team dispatch based on task state",
            "Final acceptance verification",
            "Maintain flow-context.yaml state machine",
            "Read only L1/L2 summaries, never L3 full results",
        ],
        dispatch_phase="",
    )

    if mode == TEAM_MODE_SOLO:
        return {"main": main}

    searcher = AgentTeamMember(
        role="knowledge-retrieval",
        activated=True,
        responsibilities=[
            "Query wiki INDEX.md and search all knowledge bases",
            "Search skills via Grep trigger matching",
            "Search recall for similar historical tasks",
            "WebSearch when local knowledge insufficient",
            "Return structured search results to main agent",
        ],
        dispatch_phase=DISPATCH_PHASE_THINK,
    )

    if mode == TEAM_MODE_SEARCH_ONLY:
        return {"main": main, "searcher": searcher}

    executor = AgentTeamMember(
        role="implementation",
        activated=True,
        responsibilities=[
            "Generate implementation documents",
            "Execute code changes per plan",
            "Write incremental artifacts",
            "Record process to Memory.md",
        ],
        dispatch_phase=DISPATCH_PHASE_EXECUTE,
    )

    verifier = AgentTeamMember(
        role="verification",
        activated=True,
        responsibilities=[
            "Run tests and perform acceptance verification",
            "Evidence-driven PASS/FAIL per criterion",
            "Security and regression checks",
        ],
        dispatch_phase=DISPATCH_PHASE_VERIFY,
    )

    return {
        "main": main,
        "searcher": searcher,
        "executor": executor,
        "verifier": verifier,
    }
