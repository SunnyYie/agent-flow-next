"""Backward-compatible startup context wrappers.

Deprecated compatibility layer over :mod:`agent_flow.core.runtime_context`.
"""

from __future__ import annotations

from pathlib import Path

from agent_flow.core.runtime_context import (
    RuntimeContext as StartupContext,
    collect_runtime_context,
    render_runtime_context,
)


def build_startup_context(project_dir: Path, prompt: str) -> StartupContext:
    """Build startup context using the unified runtime context collector."""
    return collect_runtime_context(project_dir, prompt, event="startup-context")


def render_startup_context_reminder(project_dir: Path, context: StartupContext) -> str:
    """Render startup context in Claude hook format."""
    return render_runtime_context(project_dir, context, target="claude-hook")
