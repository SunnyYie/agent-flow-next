"""Shared runtime execution helper for review-style pipeline stages."""

from __future__ import annotations

import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from agent_flow.core.agent_scheduler import AgentScheduler, AgentSpec
from agent_flow.core.config import (
    project_auto_run_stages,
    project_execution_commands,
)
from agent_flow.core.event_bus import HybridEventBus
from agent_flow.core.native_runtime import execute_native_stage, resolve_native_executor
from agent_flow.core.orchestrator import ORCHESTRATOR_PROMPT, WORKER_PROMPT, FlexibleOrchestrator
from agent_flow.core.runtime import diagnose_runtime
from agent_flow.core.structured_state import TaskState as OrchestratorTaskState
from agent_flow.core.structured_state import WorkerResultState


@dataclass
class StageRuntimeResult:
    """Result of optionally executing a stage through the configured runtime."""

    attempted: bool
    executed: bool
    fallback_reason: str = ""


def stage_auto_run_enabled(
    project_dir: Path,
    stage_name: str,
    cli_auto_run: bool | None = None,
    cli_prompt_only: bool = False,
) -> bool:
    """Return True when the stage should be auto-executed.

    Resolution order:
    1. ``cli_prompt_only=True`` → always False (explicit opt-out)
    2. ``cli_auto_run`` is set → use that value (explicit override)
    3. Stage in ``auto_run_stages`` config → True
    4. ``executor_command`` configured → True (implicit default)
    5. Otherwise → False (prompt-only)
    """
    if cli_prompt_only:
        return False
    if cli_auto_run is not None:
        return cli_auto_run
    if stage_name in project_auto_run_stages(project_dir):
        return True
    # Default to auto-run when executor_command is configured
    commands = project_execution_commands(project_dir)
    return bool(commands.get("executor_command"))


def maybe_execute_stage_runtime(
    project_dir: Path,
    stage_name: str,
    output_path: Path,
    metadata: list[str] | None = None,
    *,
    cli_auto_run: bool | None = None,
    cli_prompt_only: bool = False,
    cli_backend: str | None = None,
) -> StageRuntimeResult:
    """Execute a stage with the configured runtime when enabled.

    The runtime contract is:
    ``executor_command <project_dir> <stage_name> <output_path> [metadata...]``

    Parameters
    ----------
    cli_auto_run:
        When set, overrides the project config ``auto_run_stages`` entry.
        ``True`` forces auto-run; ``False`` disables it.
    cli_prompt_only:
        When ``True``, forces prompt-only mode regardless of config.
        Takes precedence over ``cli_auto_run``.
    cli_backend:
        When set, overrides the project config ``runtime_backend`` value.
        Accepted values: ``"command"``, ``"agent-scheduler"``,
        ``"orchestrator"``, ``"orchestrator+agent-scheduler"``.
    """
    if not stage_auto_run_enabled(
        project_dir, stage_name, cli_auto_run=cli_auto_run, cli_prompt_only=cli_prompt_only,
    ):
        return StageRuntimeResult(attempted=False, executed=False)

    diagnosis = diagnose_runtime(project_dir, cli_backend=cli_backend)
    backends = diagnosis.resolved_backends

    # claude-native backend: execution is driven by Claude Code hooks/commands,
    # not by the built-in executor.
    if "claude-native" in backends:
        native_executor = resolve_native_executor(project_dir)
        if native_executor is None:
            return StageRuntimeResult(
                attempted=True,
                executed=False,
                fallback_reason=(
                    "claude-native runtime delegates execution to Claude Code; "
                    "configure execution.native_executor_command or execution.native_executor: claude-cli "
                    "for end-to-end stage execution"
                ),
            )
        success, details = execute_native_stage(project_dir, stage_name, output_path, metadata, native_executor)
        if success:
            return StageRuntimeResult(attempted=True, executed=True, fallback_reason=details)
        return StageRuntimeResult(
            attempted=True,
            executed=False,
            fallback_reason=details,
        )

    commands = project_execution_commands(project_dir)
    executor_command = commands.get("executor_command")
    if not executor_command:
        return StageRuntimeResult(
            attempted=True,
            executed=False,
            fallback_reason="executor_command is not configured",
        )

    if "orchestrator" in backends:
        return _execute_orchestrator_backend(
            project_dir,
            stage_name,
            output_path,
            executor_command,
            metadata,
            use_scheduler="agent-scheduler" in backends,
        )

    scheduler_context = _prepare_scheduler_backend(
        project_dir,
        stage_name,
        output_path,
        metadata,
        enabled="agent-scheduler" in backends,
    )
    args = [*executor_command, str(project_dir), stage_name, str(output_path), *(metadata or [])]
    try:
        result = subprocess.run(
            args,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        _finalize_scheduler_backend(scheduler_context, False, str(exc))
        return StageRuntimeResult(
            attempted=True,
            executed=False,
            fallback_reason=str(exc),
        )

    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "executor failed"
        _finalize_scheduler_backend(scheduler_context, False, reason)
        return StageRuntimeResult(
            attempted=True,
            executed=False,
            fallback_reason=reason,
        )

    _finalize_scheduler_backend(scheduler_context, True, "runtime executed successfully")
    return StageRuntimeResult(attempted=True, executed=True)


@dataclass
class SchedulerContext:
    """Captured state for scheduler-backed runtime execution."""

    scheduler: AgentScheduler
    agent_name: str


def _prepare_scheduler_backend(
    project_dir: Path,
    stage_name: str,
    output_path: Path,
    metadata: list[str] | None,
    enabled: bool,
    role_override: str | None = None,
    task_description: str | None = None,
) -> SchedulerContext | None:
    """Optionally create a scheduled sub-agent around stage execution."""
    if not enabled:
        return None

    event_bus = HybridEventBus(project_dir)
    scheduler = AgentScheduler(project_dir, event_bus)
    scheduler._load_agent_states()

    role = role_override or _stage_role(stage_name)
    agent_name = f"{stage_name}-{uuid.uuid4().hex[:6]}"
    metadata_text = ", ".join(metadata or []) or "none"
    spec = AgentSpec(
        name=agent_name,
        role=role,
        task_description=task_description
        or (
            f"Execute pipeline stage '{stage_name}' for {output_path.name}. "
            f"Metadata: {metadata_text}"
        ),
    )
    record = scheduler.spawn_agent(spec)
    try:
        prompt = scheduler.get_agent_spawn_prompt(record.spec)
        prompt_path = output_path.parent / f"{stage_name}-agent-{record.spec.name}.md"
        prompt_path.write_text(prompt, encoding="utf-8")
    except Exception:
        scheduler.terminate_agent(
            record.spec.name,
            result_summary="runtime bootstrap failed before execution",
        )
        raise
    return SchedulerContext(scheduler=scheduler, agent_name=record.spec.name)


def _finalize_scheduler_backend(context: SchedulerContext | None, success: bool, summary: str) -> None:
    """Terminate the scheduled agent when runtime execution finishes."""
    if context is None:
        return
    status_summary = summary if success else f"runtime failed: {summary}"
    context.scheduler.terminate_agent(context.agent_name, result_summary=status_summary)
def _stage_role(stage_name: str) -> str:
    """Map pipeline stages to sub-agent roles."""
    role_map = {
        "plan-review": "coder",
        "plan-eng-review": "coder",
        "review": "verifier",
        "qa": "verifier",
    }
    return role_map.get(stage_name, "executor")


def _execute_orchestrator_backend(
    project_dir: Path,
    stage_name: str,
    output_path: Path,
    executor_command: list[str],
    metadata: list[str] | None,
    use_scheduler: bool,
) -> StageRuntimeResult:
    """Execute a stage through the FlexibleOrchestrator backend."""
    original_task = output_path.read_text(encoding="utf-8")
    scheduler_context = _prepare_scheduler_backend(
        project_dir,
        stage_name,
        output_path,
        metadata,
        enabled=use_scheduler,
    )
    worker_agent_contexts: dict[str, SchedulerContext] = {}

    def llm_call(prompt: str, system_prompt: str) -> str:
        return _invoke_orchestrator_llm(project_dir, executor_command, prompt, system_prompt)

    def on_worker_start(task_def: OrchestratorTaskState) -> None:
        if scheduler_context is None:
            return
        worker_output_path = output_path.parent / f"{stage_name}-worker-{task_def.task_type}.md"
        context = _prepare_scheduler_backend(
            project_dir,
            stage_name,
            worker_output_path,
            metadata=[task_def.task_type, task_def.description],
            enabled=True,
            role_override=_stage_role(stage_name),
            task_description=(
                f"Execute orchestrator worker '{task_def.task_type}' for stage '{stage_name}'. "
                f"Worker task: {task_def.description}"
            ),
        )
        if context is not None:
            worker_agent_contexts[task_def.task_id] = context

    def on_worker_complete(task_def: OrchestratorTaskState, worker_result: WorkerResultState) -> None:
        context = worker_agent_contexts.pop(task_def.task_id, None)
        if context is None:
            return
        _finalize_scheduler_backend(
            context,
            worker_result.status.value == "success",
            worker_result.result,
        )

    orchestrator = FlexibleOrchestrator(
        orchestrator_prompt=_stage_orchestrator_prompt(stage_name),
        worker_prompt=_stage_worker_prompt(stage_name),
        llm_call=llm_call,
        on_worker_start=on_worker_start,
        on_worker_complete=on_worker_complete,
    )

    try:
        try:
            result = orchestrator.process(
                original_task,
                context={
                    "stage_name": stage_name,
                    "metadata": ", ".join(metadata or []) or "none",
                },
            )
        except (OSError, RuntimeError, ValueError) as exc:
            failure_result = StageRuntimeResult(
                attempted=True,
                executed=False,
                fallback_reason=str(exc),
            )
            _finalize_scheduler_backend(scheduler_context, False, str(exc))
            return failure_result

        if result.metadata.get("error"):
            failure_result = StageRuntimeResult(
                attempted=True,
                executed=False,
                fallback_reason=str(result.metadata["error"]),
            )
            _finalize_scheduler_backend(scheduler_context, False, str(result.metadata["error"]))
            return failure_result

        output_path.write_text(_format_orchestrated_output(stage_name, result), encoding="utf-8")
        _finalize_scheduler_backend(scheduler_context, True, "orchestrator runtime executed successfully")
        return StageRuntimeResult(attempted=True, executed=True)
    finally:
        # Unified cleanup: make sure worker contexts left behind by abnormal
        # orchestrator exits are always terminated.
        for context in list(worker_agent_contexts.values()):
            _finalize_scheduler_backend(
                context,
                False,
                "orchestrator runtime ended before worker completion",
            )
        worker_agent_contexts.clear()


def _invoke_orchestrator_llm(
    project_dir: Path,
    executor_command: list[str],
    prompt: str,
    system_prompt: str,
) -> str:
    """Bridge orchestrator LLM calls through the configured executor command."""
    pipeline_dir = project_dir / ".agent-flow" / "pipeline"
    pipeline_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=pipeline_dir,
        suffix=".prompt.md",
    ) as prompt_file:
        prompt_file.write(prompt)
        prompt_path = Path(prompt_file.name)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=pipeline_dir,
        suffix=".system.md",
    ) as system_file:
        system_file.write(system_prompt)
        system_path = Path(system_file.name)

    try:
        result = subprocess.run(
            [*executor_command, str(project_dir), "orchestrator-llm", str(prompt_path), str(system_path)],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        prompt_path.unlink(missing_ok=True)
        system_path.unlink(missing_ok=True)

    if result.returncode != 0:
        reason = result.stderr.strip() or result.stdout.strip() or "orchestrator llm call failed"
        raise RuntimeError(reason)

    return result.stdout.strip()


def _format_orchestrated_output(stage_name: str, result: object) -> str:
    """Render orchestrator output into a stable markdown stage artifact."""
    lines = [
        "# Orchestrated Stage Output",
        "",
        f"**Stage**: {stage_name}",
        "",
        "## Analysis",
        "",
        getattr(result, "analysis", "") or "(no analysis)",
        "",
        "## Worker Results",
        "",
    ]

    for worker_result in getattr(result, "worker_results", []):
        lines.extend([
            f"### {worker_result.task_type}",
            "",
            worker_result.result,
            "",
        ])

    metadata = getattr(result, "metadata", {}) or {}
    if metadata:
        lines.extend([
            "## Metadata",
            "",
            f"- Total tasks: {metadata.get('total_tasks', 0)}",
            f"- Successful: {metadata.get('successful', 0)}",
            f"- Failed: {metadata.get('failed', 0)}",
            "",
        ])

    return "\n".join(lines)


def _stage_orchestrator_prompt(stage_name: str) -> str:
    """Return a stage-specific orchestrator prompt when available."""
    prompts = {
        "plan-eng-review": """\
You are an Engineering design review board coordinating a staged implementation plan.

Stage: {stage_name}
Metadata: {metadata}

Task:
{task}

Return your response in this format:

<analysis>
Explain how to split the engineering review into architecture, execution sequencing, and test strategy checks.
</analysis>

<tasks>
    <task>
    <type>architecture</type>
    <description>Review architecture boundaries, data flow, and API contracts.</description>
    </task>
    <task>
    <type>delivery</type>
    <description>Review task ordering, rollout safety, and testing completeness.</description>
    </task>
</tasks>
""",
        "review": """\
You are a paranoid senior engineer review council.

Stage: {stage_name}
Metadata: {metadata}

Task:
{task}

Return your response in this format:

<analysis>
Explain how to split the review into correctness, security, and testing-focused passes.
</analysis>

<tasks>
    <task>
    <type>correctness</type>
    <description>Inspect correctness risks, regressions, and edge cases.</description>
    </task>
    <task>
    <type>testing</type>
    <description>Inspect testing gaps and validation coverage.</description>
    </task>
</tasks>
""",
    }
    return prompts.get(stage_name, ORCHESTRATOR_PROMPT)


def _stage_worker_prompt(stage_name: str) -> str:
    """Return a stage-specific worker prompt when available."""
    prompts = {
        "plan-eng-review": """\
Stage: {stage_name}
Metadata: {metadata}
Original Task:
{original_task}

Style: {task_type}
Checklist:
{task_description}

Return your response in this format:

<response>
Provide a focused engineering review note for this sub-area, including concrete risks and implementation guidance.
</response>
""",
        "review": """\
Stage: {stage_name}
Metadata: {metadata}
Original Task:
{original_task}

Style: {task_type}
Focus:
{task_description}

Return your response in this format:

<response>
Provide concrete review findings and rationale for this review pass.
</response>
""",
    }
    return prompts.get(stage_name, WORKER_PROMPT)
