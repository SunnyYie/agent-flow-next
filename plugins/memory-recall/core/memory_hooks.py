"""Memory hook providers — hermes MemoryProvider lifecycle hooks.

Provides lifecycle hooks for the memory system: turn start, pre-compress,
session end, delegation, and memory write. Hooks are fire-and-forget:
exceptions are caught and logged to stderr, never blocking main flow.

Implements the hermes MemoryProvider concept with a registry that supports
multiple providers and a built-in DefaultMemoryHookProvider.
"""

import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent_flow.core.hook_telemetry import append_hook_telemetry


class HookContext(BaseModel):
    """Context passed to every hook invocation.

    Carries project/agent/session identity plus optional metadata.
    """

    project_dir: str = ""
    agent_name: str = "main"
    session_id: str = ""
    phase: str = ""
    metadata: dict = Field(default_factory=dict)


class MemoryHookProvider(ABC):
    """Abstract base class for memory lifecycle hook providers.

    Subclass and implement the five lifecycle hooks to integrate custom
    behaviour into the memory system.  All hooks are called in a
    fire-and-forget manner by the registry.
    """

    @abstractmethod
    def on_turn_start(self, ctx: HookContext) -> None:
        """Called at the beginning of each agent turn."""

    @abstractmethod
    def on_pre_compress(self, ctx: HookContext) -> list[dict]:
        """Called before context compression.

        Returns a list of high-confidence entries that should survive
        compression.
        """

    @abstractmethod
    def on_session_end(self, ctx: HookContext) -> None:
        """Called when the session ends.

        Triggers auto-organization checks and saves scene summaries.
        """

    @abstractmethod
    def on_delegation(self, ctx: HookContext, target_agent: str) -> None:
        """Called when the main agent delegates work to a sub-agent.

        Should copy relevant memory to the sub-agent's directory.
        """

    @abstractmethod
    def on_memory_write(self, ctx: HookContext, content: str) -> None:
        """Called after new content is written to memory.

        Should index the content to FTS5 and check skill auto-creation
        triggers.
        """


class DefaultMemoryHookProvider(MemoryHookProvider):
    """Built-in hook provider that wires lifecycle events to core managers.

    - on_turn_start: loads frozen memory snapshot, emits event
    - on_pre_compress: returns high-confidence entries that should survive
    - on_session_end: triggers auto-organization check, saves scene summary
    - on_delegation: copies relevant memory to sub-agent directory
    - on_memory_write: indexes new content to FTS5, checks skill triggers
    """

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir

    # -- lazy imports to avoid circular deps at module level ---------------

    def _frozen_memory_manager(self) -> Any:
        from agent_flow.core.frozen_memory import FrozenMemoryManager
        return FrozenMemoryManager(self.project_dir)

    def _memory_manager(self, agent_name: str = "main") -> Any:
        from agent_flow.core.memory import MemoryManager
        return MemoryManager(self.project_dir, agent_name)

    def _skill_manager(self) -> Any:
        from agent_flow.core.skill_manager import SkillManager
        return SkillManager(self.project_dir)

    # -- hook implementations ----------------------------------------------

    def on_turn_start(self, ctx: HookContext) -> None:
        """Load frozen memory snapshot for the current agent."""
        frozen_mgr = self._frozen_memory_manager()
        snapshot = frozen_mgr.load_snapshot()
        # Store the snapshot in metadata for downstream consumers
        ctx.metadata["_frozen_snapshot"] = snapshot

    def on_pre_compress(self, ctx: HookContext) -> list[dict]:
        """Return high-confidence Soul.md entries that must survive compression."""
        mm = self._memory_manager(ctx.agent_name)
        soul = mm.read_soul()
        dynamic = soul.get("dynamic", [])

        # Entries with confidence >= 0.7 survive compression
        high_confidence = [
            entry for entry in dynamic
            if entry.get("confidence", 0.0) >= 0.7
        ]
        return high_confidence

    def on_session_end(self, ctx: HookContext) -> None:
        """Trigger auto-organization check and save scene summary."""
        from agent_flow.core.evolution import EvolutionEngine
        from agent_flow.core.organizer import MemoryOrganizer
        from agent_flow.core.recall import RecallManager
        from agent_flow.core.recall_models import SceneSummary
        from agent_flow.core.reflection import build_reflection_bundle

        # 1. Save recall scene summary
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            phase_slug = ctx.phase.lower() or "session"
            summary_id = f"{today}-{phase_slug}"

            # Attempt to read task description from current_phase.md
            task_desc = ctx.phase or "session"
            phase_path = self.project_dir / ".agent-flow" / "state" / "current_phase.md"
            if phase_path.is_file():
                try:
                    content = phase_path.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        stripped = line.strip()
                        if stripped.startswith("# "):
                            task_desc = stripped[2:].strip()
                            break
                except Exception:
                    pass

            memory_rel = ".agent-flow/memory/main/Memory.md"
            reflection = build_reflection_bundle(self.project_dir, ctx.phase, task_desc)
            evolution = EvolutionEngine(self.project_dir, ctx.agent_name)
            crystallized = evolution.crystallize_from_memory(task_desc)
            stagnation = evolution.detect_stagnation()
            if stagnation is not None and stagnation.should_interrupt:
                reflection.errors_encountered.append(
                    f"检测到停滞模式: {stagnation.signature} (x{stagnation.occurrences})"
                )

            summary = SceneSummary(
                id=summary_id,
                date=today,
                task_description=task_desc,
                phases_completed=[ctx.phase] if ctx.phase else [],
                key_decisions=reflection.key_decisions,
                experiences_extracted=reflection.experiences_extracted,
                skills_created=[crystallized.skill_name] if crystallized.created and crystallized.skill_name else [],
                wiki_entries_created=[],
                errors_encountered=reflection.errors_encountered,
                outcome="completed",
                source_log=memory_rel,
                confidence=0.8 if reflection.experiences_extracted else 0.6,
            )
            recall_mgr = RecallManager(self.project_dir)
            recall_mgr.save_scene_summary(summary)
        except Exception:
            # Fire-and-forget: recall creation must not block session end
            pass

        # 2. Check organization triggers and auto-run if met
        organizer = MemoryOrganizer(self.project_dir)
        triggers = organizer.check_triggers()
        if triggers:
            # Write flag file for backward compatibility
            log_dir = self.project_dir / ".agent-flow" / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            flag_path = log_dir / "organization_pending.flag"
            flag_path.write_text(
                f"{datetime.now().isoformat()}\nTriggers: {', '.join(triggers)}\n",
                encoding="utf-8",
            )

            # Actually run organization
            try:
                organizer.run_full_organization(dry_run=False)
            except Exception:
                # Fire-and-forget: organization failure must not block session end
                pass

    def on_delegation(self, ctx: HookContext, target_agent: str) -> None:
        """Copy relevant memory from main agent to sub-agent directory."""
        main_mm = self._memory_manager("main")
        sub_mm = self._memory_manager(target_agent)

        # Copy the main agent's working memory as context for the sub-agent
        main_memory = main_mm.read_memory()
        if main_memory:
            sub_mm.append_memory(
                f"[DELEGATION CONTEXT from main]\n{main_memory[:2000]}"
            )

        # Copy high-confidence experiences from main Soul
        soul = main_mm.read_soul()
        dynamic = soul.get("dynamic", [])
        for entry in dynamic:
            if entry.get("confidence", 0.0) >= 0.8:
                sub_mm.add_experience(
                    date=entry.get("date", ""),
                    module=entry.get("module", ""),
                    exp_type=entry.get("exp_type", ""),
                    description=entry.get("description", ""),
                    confidence=entry.get("confidence", 0.0),
                    abstraction=entry.get("abstraction", ""),
                )

    def on_memory_write(self, ctx: HookContext, content: str) -> None:
        """Index new content to FTS5.

        Memory writes should not auto-create Skills. Skill promotion belongs to
        an explicit reflection/promotion pipeline after knowledge is validated.
        """
        from agent_flow.core.memory_index import index_all

        # Re-index memory sources so FTS5 is up-to-date
        db_path = str(self.project_dir / ".agent-flow" / "observations.db")
        try:
            index_all(self.project_dir, db_path)
        except Exception:
            # Indexing failure must not block writes
            pass


class MemoryHookRegistry:
    """Registry that manages multiple MemoryHookProviders.

    Hooks are fired in registration order.  All invocations are
    fire-and-forget: exceptions are caught and logged to stderr,
    never blocking the main execution flow.
    """

    def __init__(self) -> None:
        self._providers: list[MemoryHookProvider] = []

    def register(self, provider: MemoryHookProvider) -> None:
        """Register a hook provider."""
        self._providers.append(provider)

    def fire(self, hook_name: str, ctx: HookContext, **kwargs: Any) -> None:
        """Fire a named hook across all registered providers.

        Fire-and-forget: each provider call is wrapped in try/except.
        Errors are logged to stderr but never propagated.

        Telemetry is appended to .agent-flow/logs/hook_telemetry.jsonl
        (one JSON object per line).  Telemetry failures are silently
        ignored so they never affect hook execution.
        """
        fire_start = time.monotonic()
        any_error = None
        for provider in self._providers:
            try:
                method = getattr(provider, hook_name, None)
                if method is None:
                    continue
                method(ctx, **kwargs)
            except Exception as exc:
                any_error = str(exc)
                print(
                    f"[memory_hooks] Error in {provider.__class__.__name__}.{hook_name}: {exc}",
                    file=sys.stderr,
                )
        duration_ms = round((time.monotonic() - fire_start) * 1000, 2)
        self._write_telemetry(hook_name, ctx, duration_ms, any_error)

    @staticmethod
    def _write_telemetry(
        hook_name: str,
        ctx: HookContext,
        duration_ms: float,
        error: str | None,
    ) -> None:
        """Append a telemetry entry to hook_telemetry.jsonl.

        Non-blocking: any failure is silently swallowed.
        """
        try:
            project_dir = ctx.project_dir or "."
            status = "error" if error is not None else "success"
            details = {
                "phase": ctx.phase,
                "project_dir": str(project_dir),
                "agent_name": ctx.agent_name,
                "session_id": ctx.session_id,
                "source": ctx.metadata.get("source", ""),
            }
            telemetry_details = ctx.metadata.get("telemetry", {})
            if isinstance(telemetry_details, dict):
                details.update(telemetry_details)
            if error is not None:
                details["error"] = error
            append_hook_telemetry(
                Path(project_dir),
                hook_name=hook_name,
                status=status,
                duration_ms=duration_ms,
                details=details,
            )
        except Exception:
            # Telemetry must never interfere with hook execution
            pass

    @classmethod
    def from_project(cls, project_dir: Path) -> "MemoryHookRegistry":
        """Create a registry with the built-in DefaultMemoryHookProvider."""
        registry = cls()
        registry.register(DefaultMemoryHookProvider(project_dir))
        return registry
