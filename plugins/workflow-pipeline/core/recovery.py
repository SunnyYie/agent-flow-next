"""Recovery and atomic writes for the Main Agent + Sub-Agent architecture.

Handles interruption recovery by detecting interrupted workflows,
orphaned agents, and partial artifacts, then providing structured
recovery strategies. Also provides atomic file write operations
to prevent corruption on crash.
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agent_flow.core.state_contract import get_state_paths, normalize_flow_context_data


# ---------------------------------------------------------------------------
# Atomic write utility
# ---------------------------------------------------------------------------


def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write content to file atomically using write-to-temp-then-rename pattern.

    Writes to a temporary file first, then atomically renames it to the
    target path. This prevents partial writes on crash.

    Args:
        path: Target file path.
        content: Content to write.
        encoding: File encoding (default: utf-8).

    Raises:
        OSError: If write or rename fails. On rename failure, the temp file
                 is removed before re-raising.
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        tmp_path.write_text(content, encoding=encoding)
        os.replace(str(tmp_path), str(path))
    except BaseException:
        # Clean up temp file on any failure
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RecoveryStrategy(str, Enum):
    """Strategy for recovering from an interrupted workflow."""

    RETRY = "retry"  # Re-spawn failed/interrupted agents
    SKIP = "skip"    # Mark interrupted tasks as failed, continue with pending
    FRESH = "fresh"  # Reset all state, start from scratch


class InterruptedTask(BaseModel):
    """A task that was interrupted mid-execution."""

    task_id: int
    title: str = ""
    agent_name: str = ""
    partial_artifacts: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class OrphanedAgent(BaseModel):
    """An agent still marked as running whose parent workflow is gone."""

    name: str
    role: str = ""
    task_id: int = 0

    model_config = {"extra": "allow"}


class RecoveryReport(BaseModel):
    """Diagnostic report of an interrupted workflow."""

    interrupted_tasks: list[InterruptedTask] = Field(default_factory=list)
    orphaned_agents: list[OrphanedAgent] = Field(default_factory=list)
    can_recover: bool = False
    summary: str = ""

    model_config = {"extra": "allow"}


class RecoveryResult(BaseModel):
    """Outcome of a recovery operation."""

    strategy_used: RecoveryStrategy = RecoveryStrategy.RETRY
    recovered_tasks: list[int] = Field(default_factory=list)
    failed_tasks: list[int] = Field(default_factory=list)
    message: str = ""

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# Checkpoint model
# ---------------------------------------------------------------------------


class CheckpointData(BaseModel):
    """Snapshot of workflow state saved before each phase transition."""

    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    phase: str = "IDLE"
    task_states: dict[str, Any] = Field(default_factory=dict)
    agent_states: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# RecoveryManager
# ---------------------------------------------------------------------------


class RecoveryManager:
    """Handles interruption recovery and checkpoint management.

    Auto-detects the project workflow directory (.agent-flow/)
    and provides methods to detect, diagnose, and recover from interrupted
    workflows.
    """

    CHECKPOINT_FILENAME = ".checkpoint.yaml"
    FLOW_CONTEXT_FILENAME = "flow-context.yaml"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.state_paths = get_state_paths(project_dir)
        self.workflow_dir = project_dir / ".agent-flow"

    # ── Detection ────────────────────────────────────────────────

    def detect_interrupted_workflow(self) -> RecoveryReport | None:
        """Check for an interrupted workflow and return a diagnostic report.

        Reads flow-context.yaml to find tasks with status "in_progress"
        and agents with status "running". Also checks for partial artifacts
        in .agent-flow/artifacts/.

        Returns:
            RecoveryReport if an interrupted workflow is detected, None otherwise.
        """
        flow_context_path = self.state_paths.read_path(self.FLOW_CONTEXT_FILENAME)
        if not flow_context_path.is_file():
            return None

        try:
            raw = yaml.safe_load(flow_context_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(raw, dict):
            return None
        raw = normalize_flow_context_data(raw)

        interrupted_tasks: list[InterruptedTask] = []
        orphaned_agents: list[OrphanedAgent] = []

        # --- Parse tasks ---
        tasks_data = raw.get("tasks", [])
        if isinstance(tasks_data, list):
            for task in tasks_data:
                if not isinstance(task, dict):
                    continue
                if task.get("status") == "in_progress":
                    task_id = task.get("id", 0)
                    if isinstance(task_id, str):
                        try:
                            task_id = int(task_id)
                        except (ValueError, TypeError):
                            task_id = 0
                    partial = self._find_partial_artifacts(task_id)
                    interrupted_tasks.append(
                        InterruptedTask(
                            task_id=task_id,
                            title=task.get("title", ""),
                            agent_name=task.get("agent_name", ""),
                            partial_artifacts=partial,
                        )
                    )

        # --- Parse agents ---
        agents_data = raw.get("agents", [])
        if isinstance(agents_data, list):
            for agent in agents_data:
                if not isinstance(agent, dict):
                    continue
                if agent.get("status") == "running":
                    task_ref = agent.get("task_id", 0)
                    if isinstance(task_ref, str):
                        try:
                            task_ref = int(task_ref)
                        except (ValueError, TypeError):
                            task_ref = 0
                    orphaned_agents.append(
                        OrphanedAgent(
                            name=agent.get("name", ""),
                            role=agent.get("role", ""),
                            task_id=task_ref,
                        )
                    )

        if not interrupted_tasks and not orphaned_agents:
            return None

        # Determine recovery viability
        can_recover = any(
            bool(t.partial_artifacts) for t in interrupted_tasks
        ) or bool(interrupted_tasks)

        # Build human-readable summary
        parts: list[str] = []
        if interrupted_tasks:
            parts.append(f"{len(interrupted_tasks)} interrupted task(s)")
        if orphaned_agents:
            parts.append(f"{len(orphaned_agents)} orphaned agent(s)")
        summary = "; ".join(parts)

        return RecoveryReport(
            interrupted_tasks=interrupted_tasks,
            orphaned_agents=orphaned_agents,
            can_recover=can_recover,
            summary=summary,
        )

    # ── Recovery ─────────────────────────────────────────────────

    def recover(self, strategy: RecoveryStrategy) -> RecoveryResult:
        """Execute a recovery strategy on the interrupted workflow.

        Args:
            strategy: The recovery strategy to apply.

        Returns:
            RecoveryResult with details of what was recovered or failed.
        """
        report = self.detect_interrupted_workflow()
        if report is None:
            return RecoveryResult(
                strategy_used=strategy,
                message="No interrupted workflow found.",
            )

        flow_context_path = self.state_paths.read_path(self.FLOW_CONTEXT_FILENAME)
        if not flow_context_path.is_file():
            return RecoveryResult(
                strategy_used=strategy,
                message="flow-context.yaml not found during recovery.",
            )

        try:
            raw = yaml.safe_load(flow_context_path.read_text(encoding="utf-8"))
        except Exception:
            return RecoveryResult(
                strategy_used=strategy,
                message="Failed to read flow-context.yaml during recovery.",
            )

        if not isinstance(raw, dict):
            return RecoveryResult(
                strategy_used=strategy,
                message="flow-context.yaml has unexpected format.",
            )
        raw = normalize_flow_context_data(raw)

        recovered: list[int] = []
        failed: list[int] = []

        if strategy == RecoveryStrategy.RETRY:
            # Re-dispatch agents for in-progress tasks
            for task in report.interrupted_tasks:
                # Mark task as pending so it can be re-dispatched
                self._update_task_status(raw, task.task_id, "pending")
                recovered.append(task.task_id)
            # Reset orphaned agents to allow re-spawning
            raw["agents"] = [
                a for a in raw.get("agents", [])
                if isinstance(a, dict) and a.get("status") != "running"
            ]
            message = f"Re-dispatching {len(recovered)} task(s). Orphaned agents cleared."

        elif strategy == RecoveryStrategy.SKIP:
            # Mark interrupted tasks as failed, keep pending tasks
            for task in report.interrupted_tasks:
                self._update_task_status(raw, task.task_id, "failed")
                failed.append(task.task_id)
            # Remove orphaned agents
            raw["agents"] = [
                a for a in raw.get("agents", [])
                if isinstance(a, dict) and a.get("status") != "running"
            ]
            message = f"Skipped {len(failed)} task(s) as failed. Orphaned agents cleared."

        elif strategy == RecoveryStrategy.FRESH:
            # Reset all state, start from scratch
            raw["tasks"] = []
            raw["agents"] = []
            raw["phase"] = "IDLE"
            raw["started_at"] = ""
            raw["recovery"] = raw.get("recovery", {})
            if isinstance(raw["recovery"], dict):
                raw["recovery"]["last_checkpoint"] = ""
                raw["recovery"]["interrupted_task"] = 0
                raw["recovery"]["partial_artifacts"] = []
            message = "All state reset. Starting fresh."

        else:
            message = f"Unknown recovery strategy: {strategy}"

        # Persist updated flow-context.yaml atomically
        atomic_write(
            flow_context_path,
            yaml.dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True),
        )

        return RecoveryResult(
            strategy_used=strategy,
            recovered_tasks=recovered,
            failed_tasks=failed,
            message=message,
        )

    # ── Checkpoint management ────────────────────────────────────

    def create_checkpoint(self, flow_context: dict) -> None:
        """Save current state as a checkpoint before a phase transition.

        The checkpoint is written to .agent-flow/state/.checkpoint.yaml
        using atomic writes to prevent corruption.

        Args:
            flow_context: The current flow-context dict to snapshot.
        """
        checkpoint = CheckpointData(
            timestamp=datetime.now().isoformat(),
            phase=str(flow_context.get("phase", "IDLE")),
            task_states=flow_context.get("tasks", {}),
            agent_states=flow_context.get("agents", {}),
        )

        checkpoint_path = self.state_paths.write_path(self.CHECKPOINT_FILENAME)
        atomic_write(
            checkpoint_path,
            yaml.dump(
                checkpoint.model_dump(mode="json"),
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            ),
        )

    def load_last_checkpoint(self) -> CheckpointData | None:
        """Load the last checkpoint to determine state before interruption.

        Returns:
            CheckpointData if a checkpoint exists, None otherwise.
        """
        checkpoint_path = self.state_paths.read_path(self.CHECKPOINT_FILENAME)
        if not checkpoint_path.is_file():
            return None

        try:
            raw = yaml.safe_load(checkpoint_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(raw, dict):
            return None

        try:
            return CheckpointData(**raw)
        except Exception:
            return None

    # ── Private helpers ──────────────────────────────────────────

    def _find_partial_artifacts(self, task_id: int) -> list[str]:
        """Find partial artifacts for a given task in .agent-flow/artifacts/.

        Checks for:
        - task-summary.md (task partially completed)
        - task-packet.md (task was dispatched but never started)
        - task-result.md (task produced results)

        Args:
            task_id: The task ID to search artifacts for.

        Returns:
            List of artifact file paths that exist.
        """
        artifacts_dir = self.state_paths.canonical_dir.parent / "artifacts"
        if not artifacts_dir.is_dir():
            return []

        found: list[str] = []
        for pattern in [
            f"task-{task_id}-summary.md",
            f"task-{task_id}-packet.md",
            f"task-{task_id}-result.md",
        ]:
            artifact_path = artifacts_dir / pattern
            if artifact_path.exists():
                found.append(str(artifact_path.relative_to(self.workflow_dir)))

        return found

    def _update_task_status(
        self, flow_context: dict, task_id: int, new_status: str
    ) -> None:
        """Update the status of a task in the flow-context dict (in-place).

        Args:
            flow_context: The mutable flow-context dict.
            task_id: The task ID to update.
            new_status: The new status string (e.g. "pending", "failed").
        """
        tasks = flow_context.get("tasks", [])
        if not isinstance(tasks, list):
            return
        for task in tasks:
            if isinstance(task, dict) and task.get("id") == task_id:
                task["status"] = new_status
                break
