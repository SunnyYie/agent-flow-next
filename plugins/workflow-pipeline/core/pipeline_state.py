"""Pipeline state models — Pydantic models for the development pipeline.

Tracks the full lifecycle from plan-review through ship,
with per-stage status, task tracking, and output references.
"""

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    """Status of a pipeline stage."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReviewMode(str, Enum):
    """Review mode for plan-review command."""

    EXPANSION = "expansion"
    SELECTIVE = "selective"
    HOLD = "hold"
    REDUCTION = "reduction"


class ReviewVerdict(str, Enum):
    """Verdict from a review stage."""

    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


class TaskComplexity(str, Enum):
    """Complexity level for a task."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskState(BaseModel):
    """State of a single task within the /run stage."""

    id: int
    title: str = ""
    description: str = ""
    status: StageStatus = StageStatus.PENDING
    verified: bool = False
    files: list[str] = Field(default_factory=list)
    dependencies: list[int] = Field(default_factory=list)
    test_criteria: list[str] = Field(default_factory=list)
    complexity: TaskComplexity = TaskComplexity.MEDIUM
    phase: int = 1
    retry_count: int = 0
    commit_sha: str = ""


class StageState(BaseModel):
    """State of a pipeline stage."""

    status: StageStatus = StageStatus.PENDING
    completed_at: str = ""
    output: Any = ""  # str (file path) or dict (e.g., {"branch": "feature/x"})
    verdict: str = ""  # For review stages: approved/needs_revision/rejected
    started_at: str = ""


# The canonical order of pipeline stages
PIPELINE_STAGE_ORDER = [
    "plan-review",
    "plan-eng-review",
    "add-feature",
    "run",
    "review",
    "qa",
    "ship",
]

# Stages that are optional — skipped by default unless user explicitly requests them
OPTIONAL_STAGES = {"plan-review"}

# Required stages that must be completed before ship
REQUIRED_STAGES_FOR_SHIP = ["add-feature", "review", "qa"]


class PipelineState(BaseModel):
    """Full pipeline state persisted to .agent-flow/pipeline/pipeline.yaml."""

    id: str = ""
    feature_name: str = ""
    branch: str = ""
    base_branch: str = "main"
    created_at: str = ""
    review_mode: ReviewMode = ReviewMode.HOLD
    scope: str = "frontend"  # Implementation scope: "frontend" (default) or "full"

    stages: dict[str, StageState] = Field(default_factory=lambda: {
        stage: StageState() for stage in PIPELINE_STAGE_ORDER
    })

    tasks: list[TaskState] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class PipelineManager:
    """Manages pipeline state, stage transitions, and output files.

    The pipeline.yaml file in .agent-flow/pipeline/ is the single source
    of truth for pipeline progress across all commands.
    """

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.pipeline_dir = project_dir / ".agent-flow" / "pipeline"
        self.state_path = self.pipeline_dir / "pipeline.yaml"

    def load_state(self) -> PipelineState:
        """Load pipeline state from YAML file."""
        if not self.state_path.is_file():
            return PipelineState()
        try:
            data = yaml.safe_load(self.state_path.read_text(encoding="utf-8")) or {}
            return PipelineState(**data)
        except Exception:
            return PipelineState()

    def save_state(self, state: PipelineState) -> None:
        """Save pipeline state to YAML file."""
        self.pipeline_dir.mkdir(parents=True, exist_ok=True)
        data = state.model_dump(mode="json", exclude_none=True)
        self.state_path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        self._sync_completed_tasks(state)

    def init_pipeline(self, feature_name: str, branch: str, base_branch: str = "main") -> PipelineState:
        """Initialize a new pipeline for a feature."""
        from datetime import datetime

        state = PipelineState(
            id=f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{feature_name}",
            feature_name=feature_name,
            branch=branch,
            base_branch=base_branch,
            created_at=datetime.now().isoformat(),
        )
        self.save_state(state)
        return state

    def start_stage(self, stage_name: str) -> PipelineState:
        """Mark a stage as in_progress."""
        from datetime import datetime

        state = self.load_state()
        if stage_name not in state.stages:
            state.stages[stage_name] = StageState()
        state.stages[stage_name].status = StageStatus.IN_PROGRESS
        state.stages[stage_name].started_at = datetime.now().isoformat()
        self.save_state(state)
        return state

    def complete_stage(
        self, stage_name: str, verdict: str = "", output: Any = ""
    ) -> PipelineState:
        """Mark a stage as completed."""
        from datetime import datetime

        state = self.load_state()
        if stage_name not in state.stages:
            state.stages[stage_name] = StageState()
        state.stages[stage_name].status = StageStatus.COMPLETED
        state.stages[stage_name].completed_at = datetime.now().isoformat()
        state.stages[stage_name].verdict = verdict
        state.stages[stage_name].output = output
        self.save_state(state)
        return state

    def fail_stage(self, stage_name: str, reason: str = "") -> PipelineState:
        """Mark a stage as failed."""
        from datetime import datetime

        state = self.load_state()
        if stage_name not in state.stages:
            state.stages[stage_name] = StageState()
        state.stages[stage_name].status = StageStatus.FAILED
        state.stages[stage_name].completed_at = datetime.now().isoformat()
        state.stages[stage_name].output = reason
        self.save_state(state)
        return state

    def skip_stage(self, stage_name: str) -> PipelineState:
        """Mark a stage as skipped."""
        state = self.load_state()
        if stage_name not in state.stages:
            state.stages[stage_name] = StageState()
        state.stages[stage_name].status = StageStatus.SKIPPED
        self.save_state(state)
        return state

    def can_start_stage(self, stage_name: str) -> tuple[bool, list[str]]:
        """Check if a stage can be started based on prerequisites.

        Returns (can_start, list_of_missing_prerequisites).
        """
        state = self.load_state()
        stage_index = PIPELINE_STAGE_ORDER.index(stage_name) if stage_name in PIPELINE_STAGE_ORDER else -1

        if stage_index < 0:
            return False, [f"Unknown stage: {stage_name}"]

        # Check if already completed or in progress
        current = state.stages.get(stage_name)
        if current and current.status in (StageStatus.COMPLETED, StageStatus.IN_PROGRESS):
            return False, [f"Stage {stage_name} is already {current.status.value}"]

        # Check if all preceding non-skipped stages are completed
        missing = []
        for i in range(stage_index):
            prev_stage = PIPELINE_STAGE_ORDER[i]
            prev_state = state.stages.get(prev_stage)
            # Optional stages are auto-skipped if not completed
            if prev_stage in OPTIONAL_STAGES:
                if not prev_state or prev_state.status not in (StageStatus.COMPLETED, StageStatus.SKIPPED):
                    continue  # Skip optional stages that haven't been run
                continue
            if not prev_state or prev_state.status not in (StageStatus.COMPLETED, StageStatus.SKIPPED):
                missing.append(prev_stage)

        if missing:
            return False, missing

        return True, []

    def is_pipeline_complete(self) -> bool:
        """Check if all required stages are completed."""
        state = self.load_state()
        for stage_name in REQUIRED_STAGES_FOR_SHIP:
            stage = state.stages.get(stage_name)
            if not stage or stage.status != StageStatus.COMPLETED:
                return False
        return True

    def get_previous_stage_output(self, stage_name: str) -> str:
        """Get the output file path from the previous completed stage."""
        state = self.load_state()
        stage_index = PIPELINE_STAGE_ORDER.index(stage_name) if stage_name in PIPELINE_STAGE_ORDER else -1

        if stage_index <= 0:
            return ""

        # Walk backwards to find the most recent completed stage with output
        for i in range(stage_index - 1, -1, -1):
            prev_stage = PIPELINE_STAGE_ORDER[i]
            prev_state = state.stages.get(prev_stage)
            if prev_state and prev_state.status == StageStatus.COMPLETED and prev_state.output:
                output = prev_state.output
                if isinstance(output, str):
                    return str(self.pipeline_dir / output) if not Path(output).is_absolute() else output
                elif isinstance(output, dict):
                    return str(output)

        return ""

    def get_stage_output_path(self, stage_name: str) -> Path:
        """Get the output file path for a stage."""
        output_files = {
            "plan-review": "plan-review.md",
            "plan-eng-review": "eng-review.md",
            "run": "run-log.md",
            "review": "review-report.md",
            "qa": "qa-report.md",
            "ship": "ship-report.md",
        }
        filename = output_files.get(stage_name, f"{stage_name}.md")
        return self.pipeline_dir / filename

    def validate_prerequisites(self, stage_name: str) -> list[str]:
        """Validate that all prerequisites for a stage are met.

        Returns list of issues (empty = all good).
        """
        issues: list[str] = []

        # Check git branch matches pipeline branch
        state = self.load_state()
        if state.branch:
            try:
                import subprocess

                current_branch = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_dir,
                ).stdout.strip()
                if current_branch and current_branch != state.branch:
                    issues.append(
                        f"Current branch '{current_branch}' does not match pipeline branch '{state.branch}'"
                    )
            except Exception:
                pass

        # Check stage prerequisites
        can_start, missing = self.can_start_stage(stage_name)
        if not can_start:
            issues.extend([f"Prerequisite stage '{m}' not completed" for m in missing])

        return issues

    def update_task(self, task_id: int, **kwargs: Any) -> PipelineState:
        """Update a specific task's state."""
        state = self.load_state()
        for task in state.tasks:
            if task.id == task_id:
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                break
        self.save_state(state)
        return state

    def set_tasks(self, tasks: list[TaskState]) -> PipelineState:
        """Replace all tasks in the pipeline state."""
        state = self.load_state()
        state.tasks = tasks
        self.save_state(state)
        return state

    def get_pending_tasks(self) -> list[TaskState]:
        """Get all pending tasks sorted by dependencies (topological order)."""
        state = self.load_state()
        pending = [t for t in state.tasks if t.status == StageStatus.PENDING]

        # Topological sort by dependencies
        completed_ids = {t.id for t in state.tasks if t.status == StageStatus.COMPLETED}
        sorted_tasks: list[TaskState] = []
        remaining = list(pending)

        while remaining:
            ready = [t for t in remaining if all(d in completed_ids for d in t.dependencies)]
            if not ready:
                # Circular dependency — just add remaining in order
                sorted_tasks.extend(remaining)
                break
            sorted_tasks.extend(ready)
            for t in ready:
                completed_ids.add(t.id)
                remaining.remove(t)

        return sorted_tasks

    def _sync_completed_tasks(self, state: PipelineState) -> None:
        """Persist a human-readable completed task summary beside canonical state."""
        state_dir = self.project_dir / ".agent-flow" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        completed_path = state_dir / "completed_tasks.md"

        completed_stages: list[tuple[str, StageState]] = [
            (name, stage)
            for name, stage in state.stages.items()
            if stage.status in (StageStatus.COMPLETED, StageStatus.SKIPPED, StageStatus.FAILED)
        ]
        completed_run_tasks = [
            task for task in state.tasks
            if task.status in (StageStatus.COMPLETED, StageStatus.SKIPPED, StageStatus.FAILED)
        ]

        lines = [
            "# Completed Tasks",
            "",
            f"- Pipeline: `{state.id or 'uninitialized'}`",
            f"- Feature: `{state.feature_name or 'n/a'}`",
            f"- Branch: `{state.branch or 'n/a'}`",
            "",
            "## Stage Summary",
        ]

        if completed_stages:
            for stage_name, stage in completed_stages:
                suffix = f" — `{stage.output}`" if stage.output else ""
                verdict = f" ({stage.verdict})" if stage.verdict else ""
                lines.append(f"- `{stage_name}`: {stage.status.value}{verdict}{suffix}")
        else:
            lines.append("- No stages completed yet.")

        lines.extend(["", "## Run Task Summary"])
        if completed_run_tasks:
            for task in completed_run_tasks:
                verification = "verified" if task.verified else "unverified"
                lines.append(
                    f"- `T{task.id}` {task.title or 'Untitled'}: {task.status.value} ({verification})"
                )
        else:
            lines.append("- No run tasks completed yet.")

        completed_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
