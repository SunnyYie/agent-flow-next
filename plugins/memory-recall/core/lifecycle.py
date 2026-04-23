"""Unified lifecycle hook dispatcher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_flow.core.memory_hooks import HookContext, MemoryHookRegistry


def fire_lifecycle_event(
    project_dir: Path,
    hook_name: str,
    *,
    agent_name: str = "main",
    phase: str = "",
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> None:
    """Fire a lifecycle hook via the shared dispatcher."""
    registry = MemoryHookRegistry.from_project(project_dir)
    ctx = HookContext(
        project_dir=str(project_dir),
        agent_name=agent_name,
        phase=phase,
        metadata=metadata or {},
    )
    registry.fire(hook_name, ctx, **kwargs)


def fire_turn_start(project_dir: Path, *, agent_name: str = "main", phase: str = "", metadata: dict[str, Any] | None = None) -> None:
    fire_lifecycle_event(project_dir, "on_turn_start", agent_name=agent_name, phase=phase, metadata=metadata)


def fire_delegation(
    project_dir: Path,
    *,
    agent_name: str = "main",
    phase: str = "",
    target_agent: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    fire_lifecycle_event(
        project_dir,
        "on_delegation",
        agent_name=agent_name,
        phase=phase,
        metadata=metadata,
        target_agent=target_agent,
    )


def fire_memory_write(project_dir: Path, *, agent_name: str = "main", content: str, metadata: dict[str, Any] | None = None) -> None:
    fire_lifecycle_event(
        project_dir,
        "on_memory_write",
        agent_name=agent_name,
        metadata=metadata,
        content=content,
    )


def fire_session_end(project_dir: Path, *, agent_name: str = "main", phase: str = "", metadata: dict[str, Any] | None = None) -> None:
    fire_lifecycle_event(project_dir, "on_session_end", agent_name=agent_name, phase=phase, metadata=metadata)


def fire_pre_compress(project_dir: Path, *, agent_name: str = "main", phase: str = "", metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Fire the on_pre_compress hook and collect high-confidence entries.

    Unlike other lifecycle events, this one returns data: a list of
    high-confidence Soul.md entries that must survive context compression.
    """
    registry = MemoryHookRegistry.from_project(project_dir)
    ctx = HookContext(
        project_dir=str(project_dir),
        agent_name=agent_name,
        phase=phase,
        metadata=metadata or {},
    )
    entries: list[dict[str, Any]] = []
    for provider in registry._providers:
        try:
            method = getattr(provider, "on_pre_compress", None)
            if method is None:
                continue
            result = method(ctx)
            if isinstance(result, list):
                entries.extend(result)
        except Exception:
            pass
    return entries
