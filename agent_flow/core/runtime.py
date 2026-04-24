"""Runtime resolution and diagnostics for agent-flow.

Provides a single source of truth for determining which runtime backend
is configured, which is effective, and why.  Used by both ``doctor`` and
``run`` so that runtime truth is never ambiguous.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

from agent_flow.core.config import (
    CLAUDE_PROJECT_COMMANDS,
    project_execution_commands,
    project_runtime_backend,
    project_runtime_backends,
)
from agent_flow.core.native_runtime import (
    resolve_native_executor,
    summarize_bridge_health,
    summarize_native_agent_adoption,
)


@dataclass
class RuntimeDiagnosis:
    """Structured result of runtime resolution for a project."""

    configured_backend: str
    resolved_backends: set[str]
    effective_runtime: str
    effective_runtime_family: str
    executor_command_source: str
    native_runtime_requested: bool
    native_readiness: str
    native_adoption: str
    native_executor_mode: str  # "command", "claude-cli bridge", or "none"
    native_executor_source: str  # where the native executor config came from
    bridge_health: str
    fallback_permitted: bool
    resolution_reason: str


def diagnose_runtime(project_dir: Path, cli_backend: str | None = None) -> RuntimeDiagnosis:
    """Determine the configured and effective runtime for *project_dir*."""
    configured_backend = project_runtime_backend(project_dir)
    native_runtime_requested = configured_backend == "claude-native"
    resolved_backends = _resolve_backends(project_dir, cli_backend)
    fallback_permitted = cli_backend is not None
    commands = project_execution_commands(project_dir)
    executor_command = commands.get("executor_command")
    explicitly_configured_executor = _has_explicit_executor_command(project_dir)

    native_executor = resolve_native_executor(project_dir)
    if native_executor:
        native_executor_mode = (
            "claude-cli bridge" if native_executor.mode == "claude-cli" else native_executor.mode
        )
        native_executor_source = native_executor.source
    else:
        native_executor_mode = "none"
        native_executor_source = "no native executor configured"

    if "claude-native" in resolved_backends:
        effective_runtime = "claude-native"
        effective_runtime_family = "claude-native"
        logger.info("claude-native is the primary runtime path")
        executor_command_source = "disabled because claude-native runtime is configured"
        native_readiness = _native_readiness(project_dir)
        native_adoption = summarize_native_agent_adoption(project_dir)
        resolution_reason = (
            "explicit CLI --backend override selected claude-native runtime"
            if cli_backend is not None
            else "configured backend requests claude-native runtime"
        )
    elif executor_command:
        if explicitly_configured_executor:
            effective_runtime = "configured executor command"
            effective_runtime_family = "configured executor command"
            executor_command_source = (
                "project execution.executor_command"
                if cli_backend is None
                else "project execution.executor_command with explicit CLI --backend override"
            )
        else:
            effective_runtime = "built-in executor"
            effective_runtime_family = "built-in executor"
            executor_command_source = (
                "auto-detected from LLM configuration"
                if cli_backend is None
                else "auto-detected from LLM configuration with explicit CLI --backend override"
            )
        native_readiness = "not requested"
        native_adoption = "not requested"
        resolution_reason = (
            f"explicit CLI --backend override selected { _format_backend_set(resolved_backends) }"
            if cli_backend is not None
            else "configured runtime uses executor-backed execution"
        )
    else:
        effective_runtime = "prompt-only"
        effective_runtime_family = "prompt-only"
        executor_command_source = "no executor command resolved"
        native_readiness = "not requested"
        native_adoption = "not requested"
        resolution_reason = (
            f"explicit CLI --backend override selected { _format_backend_set(resolved_backends) }, "
            "but no executor command resolved"
            if cli_backend is not None
            else "no executor command resolved for configured runtime"
        )
    bridge_health = summarize_bridge_health(project_dir, native_executor)

    return RuntimeDiagnosis(
        configured_backend=configured_backend,
        resolved_backends=resolved_backends,
        effective_runtime=effective_runtime,
        effective_runtime_family=effective_runtime_family,
        executor_command_source=executor_command_source,
        native_runtime_requested=native_runtime_requested,
        native_readiness=native_readiness,
        native_adoption=native_adoption,
        native_executor_mode=native_executor_mode,
        native_executor_source=native_executor_source,
        bridge_health=bridge_health,
        fallback_permitted=fallback_permitted,
        resolution_reason=resolution_reason,
    )


def format_runtime_status(diagnosis: RuntimeDiagnosis) -> list[str]:
    """Render a human-readable runtime status block."""
    return [
        "Runtime status:",
        f"  Configured backend: {diagnosis.configured_backend}",
        f"  Resolved backends: {_format_backend_set(diagnosis.resolved_backends)}",
        f"  Effective runtime: {diagnosis.effective_runtime}",
        f"  Effective runtime family: {diagnosis.effective_runtime_family}",
        f"  Executor command source: {diagnosis.executor_command_source}",
        f"  Native runtime requested: {'yes' if diagnosis.native_runtime_requested else 'no'}",
        f"  Native readiness: {diagnosis.native_readiness}",
        f"  Native adoption: {diagnosis.native_adoption}",
        f"  Native executor mode: {diagnosis.native_executor_mode}",
        f"  Native executor source: {diagnosis.native_executor_source}",
        f"  Bridge health: {diagnosis.bridge_health}",
        f"  Fallback permitted: {'yes' if diagnosis.fallback_permitted else 'no'}",
        f"  Resolution reason: {diagnosis.resolution_reason}",
    ]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _has_explicit_executor_command(project_dir: Path) -> bool:
    """Return True when an explicit executor_command is configured in the project."""
    config_path = project_dir / ".agent-flow" / "config.yaml"
    if not config_path.is_file():
        return False

    try:
        import yaml

        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False

    execution = data.get("execution")
    if not isinstance(execution, dict):
        return False

    value = execution.get("executor_command")
    return isinstance(value, list) and bool(value) and all(isinstance(part, str) for part in value)


def _native_readiness(project_dir: Path) -> str:
    """Check whether claude-native runtime dependencies are present and observed."""
    from agent_flow.core.native_runtime import discover_native_agents

    commands_dir = project_dir / ".claude" / "commands"
    if not commands_dir.exists():
        return "missing .claude/commands directory"

    missing = []
    for command_name in CLAUDE_PROJECT_COMMANDS:
        command_path = commands_dir / f"agent-flow-{command_name}.md"
        if not command_path.is_file():
            missing.append(command_path.name)

    if missing:
        return f"missing command files: {', '.join(missing)}"

    available_agents = {agent.name for agent in discover_native_agents()}
    required_agents = {"executor", "verifier"}
    missing_agents = sorted(required_agents - available_agents)
    if missing_agents:
        return f"missing native agents: {', '.join(missing_agents)}"
    adoption = summarize_native_agent_adoption(project_dir)
    if adoption == "installed-unverified":
        return "installed (commands and agents present; adoption unverified)"
    return f"installed and observed ({adoption})"


def _resolve_backends(project_dir: Path, cli_backend: str | None) -> set[str]:
    """Resolve runtime backends from CLI override or project config."""
    if cli_backend is not None:
        return _parse_backend_list(cli_backend)
    return project_runtime_backends(project_dir)


def _parse_backend_list(raw_value: str) -> set[str]:
    """Parse a backend specification string (e.g. 'a+b,c') into a normalized set."""
    separators = ["+", ",", " "]
    values = [raw_value]
    for separator in separators:
        expanded: list[str] = []
        for value in values:
            expanded.extend(value.split(separator))
        values = expanded
    normalized = {value.strip() for value in values if value.strip()}
    return normalized or {"command"}


def _format_backend_set(backends: set[str]) -> str:
    """Render a set of backends as a '+'-joined string."""
    return "+".join(sorted(backends))
