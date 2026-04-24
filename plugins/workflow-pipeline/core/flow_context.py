"""FlowContextManager — Manages flow-context.yaml for the Main Agent + Sub-Agent architecture.

Analogous to PipelineManager but for the flow-based workflow:
  - Tracks workflow phase (IDLE → PLAN → EXECUTE → VERIFY → REFLECT)
  - Manages task dependencies and readiness
  - Monitors context budget across agents
  - Supports crash recovery via checkpoint state

The flow-context.yaml file in .agent-flow/state/ (or .dev-workflow/state/)
is the single source of truth for flow progress across all agents.
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agent_flow.core.state_contract import (
    DEFAULT_FLOW_CONTEXT_SCHEMA_VERSION,
    default_flow_context_data,
    get_state_paths,
    normalize_flow_context_data,
)


# ── Enums ────────────────────────────────────────────────────────


class FlowTaskStatus(str, Enum):
    """Status of a flow task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class FlowPhase(str, Enum):
    """Workflow phase for the Main Agent lifecycle."""

    IDLE = "IDLE"
    TEAM_INIT = "TEAM_INIT"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    REFLECT = "REFLECT"


class AgentRole(str, Enum):
    """Role of a sub-agent in the flow."""

    EXECUTOR = "executor"
    VERIFIER = "verifier"
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    SEARCHER = "searcher"


class AgentStatus(str, Enum):
    """Status of a sub-agent."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BudgetStatus(str, Enum):
    """Context budget health status."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"


# ── Pydantic Models ──────────────────────────────────────────────


class FlowTaskState(BaseModel):
    """State of a single task within a flow workflow.

    Each task has an L1 one-line summary and an L2 artifact file
    for the detailed result.
    """

    id: int
    title: str = ""
    status: FlowTaskStatus = FlowTaskStatus.PENDING
    agent_name: str = ""
    summary: str = ""  # L1 one-line summary
    artifact_path: str = ""  # Path to L2 summary file
    depends_on: list[int] = Field(default_factory=list)
    verified: bool = False
    verification_path: str = ""
    assigned_files: list[str] = Field(default_factory=list, description="Files owned by this task's executor")


class FlowAgentState(BaseModel):
    """State of a sub-agent participating in the flow."""

    name: str
    role: AgentRole = AgentRole.EXECUTOR
    status: AgentStatus = AgentStatus.RUNNING
    task_id: int = 0
    started_at: str = ""
    completed_at: str = ""


class ContextBudget(BaseModel):
    """Tracks context window usage across agents.

    The default max (200000) matches Claude's context window.
    Status is auto-computed: healthy (<70%), warning (70-90%), critical (>90%).
    """

    used: int = 0
    max: int = 200000
    status: BudgetStatus = BudgetStatus.HEALTHY
    files_read: int = 0
    last_update: str = ""


class RecoveryState(BaseModel):
    """Crash recovery state for resuming interrupted workflows."""

    last_checkpoint: str = ""
    interrupted_task: int = 0
    partial_artifacts: list[str] = Field(default_factory=list)


class FlowContext(BaseModel):
    """Full flow context persisted to flow-context.yaml.

    This is the top-level model that captures the entire workflow state
    including tasks, agents, context budget, and recovery information.
    """

    schema_version: int = DEFAULT_FLOW_CONTEXT_SCHEMA_VERSION
    workflow_id: str = ""
    phase: FlowPhase = FlowPhase.IDLE
    started_at: str = ""
    context_budget: ContextBudget = Field(default_factory=ContextBudget)
    tasks: list[FlowTaskState] = Field(default_factory=list)
    agents: list[FlowAgentState] = Field(default_factory=list)
    recovery: RecoveryState = Field(default_factory=RecoveryState)
    team_config: dict = Field(default_factory=dict, description="Agent team configuration from agent-team-config.yaml")

    model_config = {"extra": "allow"}


# ── FlowContextManager ───────────────────────────────────────────


class FlowContextManager:
    """Manages flow-context.yaml for the Main Agent + Sub-Agent workflow.

    Provides CRUD operations for tasks, agents, and budget tracking.
    Uses atomic writes (write to .tmp then os.replace) for crash safety.
    Auto-detects .agent-flow/state/ or .dev-workflow/state/ for compatibility.
    """

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.state_paths = get_state_paths(project_dir)
        self.state_dir = self.state_paths.canonical_dir
        self.state_path = self.state_paths.write_path("flow-context.yaml")

    # ── Persistence ──────────────────────────────────────────────

    def load(self) -> FlowContext:
        """Load flow context from YAML file.

        Returns an empty FlowContext if the file does not exist or
        cannot be parsed.
        """
        source_path = self.state_paths.read_path("flow-context.yaml")
        if not source_path.is_file():
            return FlowContext()
        try:
            data = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
            data = normalize_flow_context_data(data)
            return FlowContext(**data)
        except Exception:
            return FlowContext()

    def save(self, context: FlowContext) -> None:
        """Save flow context to YAML file using atomic write.

        Writes to a .tmp file first, then uses os.replace() for
        crash safety (atomic on POSIX systems).
        """
        self.state_dir.mkdir(parents=True, exist_ok=True)

        tmp_path = self.state_path.with_suffix(".yaml.tmp")
        data = context.model_dump(mode="json", exclude_none=True)
        yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

        tmp_path.write_text(yaml_str, encoding="utf-8")
        os.replace(str(tmp_path), str(self.state_path))

    # ── Workflow Lifecycle ───────────────────────────────────────

    def init_workflow(self, workflow_id: str) -> FlowContext:
        """Initialize a new flow workflow.

        Creates a fresh FlowContext with the given workflow_id,
        sets phase to PLAN, and persists it.

        Args:
            workflow_id: Unique identifier for this workflow run.

        Returns:
            The newly created FlowContext.
        """
        now = datetime.now().isoformat()
        payload = default_flow_context_data(workflow_id=workflow_id, phase=FlowPhase.PLAN.value)
        payload["started_at"] = now
        payload["context_budget"]["last_update"] = now
        payload["recovery"]["last_checkpoint"] = now
        context = FlowContext(**payload)
        self.save(context)
        return context

    # ── Task Operations ──────────────────────────────────────────

    def add_task(self, title: str, depends_on: list[int] | None = None) -> FlowTaskState:
        """Add a new task to the workflow.

        Task ID is auto-assigned as the next sequential integer.

        Args:
            title: One-line description of the task.
            depends_on: List of task IDs that must complete before this task.

        Returns:
            The newly created FlowTaskState.
        """
        context = self.load()
        next_id = max((t.id for t in context.tasks), default=0) + 1
        task = FlowTaskState(
            id=next_id,
            title=title,
            depends_on=depends_on or [],
        )
        context.tasks.append(task)
        self.save(context)
        return task

    def start_task(self, task_id: int, agent_name: str, role: str) -> FlowTaskState:
        """Mark a task as in_progress and assign it to an agent.

        Args:
            task_id: The task to start.
            agent_name: Name of the agent taking this task.
            role: Role of the agent (executor|verifier|researcher|analyst).

        Returns:
            The updated FlowTaskState.

        Raises:
            ValueError: If the task_id is not found.
        """
        context = self.load()
        for task in context.tasks:
            if task.id == task_id:
                task.status = FlowTaskStatus.IN_PROGRESS
                task.agent_name = agent_name
                self.save(context)
                return task
        raise ValueError(f"Task {task_id} not found")

    def complete_task(self, task_id: int, summary: str, artifact_path: str) -> FlowTaskState:
        """Mark a task as completed with its L1 summary and L2 artifact path.

        Args:
            task_id: The task to complete.
            summary: L1 one-line summary of the result.
            artifact_path: Path to the L2 detailed summary file.

        Returns:
            The updated FlowTaskState.

        Raises:
            ValueError: If the task_id is not found.
        """
        context = self.load()
        for task in context.tasks:
            if task.id == task_id:
                task.status = FlowTaskStatus.COMPLETED
                task.summary = summary
                task.artifact_path = artifact_path
                self.save(context)
                return task
        raise ValueError(f"Task {task_id} not found")

    def fail_task(self, task_id: int) -> FlowTaskState:
        """Mark a task as failed.

        Args:
            task_id: The task to mark as failed.

        Returns:
            The updated FlowTaskState.

        Raises:
            ValueError: If the task_id is not found.
        """
        context = self.load()
        for task in context.tasks:
            if task.id == task_id:
                task.status = FlowTaskStatus.FAILED
                self.save(context)
                return task
        raise ValueError(f"Task {task_id} not found")

    # ── Agent Operations ─────────────────────────────────────────

    def spawn_agent(self, name: str, role: str, task_id: int) -> FlowAgentState:
        """Register a new sub-agent as running.

        Args:
            name: Unique name for this agent instance.
            role: Agent role (executor|verifier|researcher|analyst).
            task_id: The task this agent is assigned to.

        Returns:
            The newly created FlowAgentState.
        """
        context = self.load()
        agent = FlowAgentState(
            name=name,
            role=AgentRole(role),
            status=AgentStatus.RUNNING,
            task_id=task_id,
            started_at=datetime.now().isoformat(),
        )
        context.agents.append(agent)
        self.save(context)
        return agent

    def complete_agent(self, name: str) -> FlowAgentState:
        """Mark an agent as completed.

        Args:
            name: The agent name to complete.

        Returns:
            The updated FlowAgentState.

        Raises:
            ValueError: If the agent name is not found.
        """
        context = self.load()
        for agent in context.agents:
            if agent.name == name:
                agent.status = AgentStatus.COMPLETED
                agent.completed_at = datetime.now().isoformat()
                self.save(context)
                return agent
        raise ValueError(f"Agent '{name}' not found")

    def fail_agent(self, name: str) -> FlowAgentState:
        """Mark an agent as failed.

        Args:
            name: The agent name to mark as failed.

        Returns:
            The updated FlowAgentState.

        Raises:
            ValueError: If the agent name is not found.
        """
        context = self.load()
        for agent in context.agents:
            if agent.name == name:
                agent.status = AgentStatus.FAILED
                agent.completed_at = datetime.now().isoformat()
                self.save(context)
                return agent
        raise ValueError(f"Agent '{name}' not found")

    # ── Budget Operations ────────────────────────────────────────

    def update_budget(self, tokens_used: int) -> ContextBudget:
        """Update the context budget and recompute status.

        Status thresholds:
          - healthy:  used < 70% of max
          - warning:  70% <= used < 90% of max
          - critical: used >= 90% of max

        Args:
            tokens_used: Total tokens consumed so far.

        Returns:
            The updated ContextBudget.
        """
        context = self.load()
        budget = context.context_budget
        budget.used = tokens_used
        budget.last_update = datetime.now().isoformat()

        # Recompute status
        ratio = budget.used / budget.max if budget.max > 0 else 0.0
        if ratio >= 0.9:
            budget.status = BudgetStatus.CRITICAL
        elif ratio >= 0.7:
            budget.status = BudgetStatus.WARNING
        else:
            budget.status = BudgetStatus.HEALTHY

        self.save(context)
        return budget

    # ── Query Operations ─────────────────────────────────────────

    def get_ready_tasks(self) -> list[FlowTaskState]:
        """Get tasks whose dependencies are all completed.

        Returns pending tasks where every task in depends_on has
        FlowTaskStatus.COMPLETED, sorted by ID.
        """
        context = self.load()
        completed_ids = {
            t.id for t in context.tasks if t.status == FlowTaskStatus.COMPLETED
        }
        ready = [
            t
            for t in context.tasks
            if t.status == FlowTaskStatus.PENDING
            and all(dep in completed_ids for dep in t.depends_on)
        ]
        return sorted(ready, key=lambda t: t.id)

    def get_active_agent_count(self) -> int:
        """Count the number of currently running agents."""
        context = self.load()
        return sum(1 for a in context.agents if a.status == AgentStatus.RUNNING)

    # ── Phase Operations ─────────────────────────────────────────

    def set_phase(self, phase: str) -> FlowContext:
        """Update the workflow phase.

        Args:
            phase: New phase value (IDLE|PLAN|EXECUTE|VERIFY|REFLECT).

        Returns:
            The updated FlowContext.
        """
        context = self.load()
        context.phase = FlowPhase(phase)
        # Update recovery checkpoint on phase transitions
        context.recovery.last_checkpoint = datetime.now().isoformat()
        self.save(context)
        return context

    # ── Artifact Path ────────────────────────────────────────────

    def get_artifact_path(self, task_id: int, suffix: str) -> Path:
        """Get the artifact file path for a task.

        Artifacts are stored in the state directory with the pattern
        task-{task_id}-{suffix}. For example: task-1-summary.md

        Args:
            task_id: The task ID.
            suffix: Artifact suffix (e.g., "summary.md", "verification.md").

        Returns:
            Absolute path to the artifact file.
        """
        return self.state_dir / f"task-{task_id}-{suffix}"
