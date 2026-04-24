"""Unified runtime context collection and rendering.

Provides a single source of truth for startup/runtime context used by
Claude hooks, built-in executors, and diagnostics.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_flow.core.config import project_runtime_backend
from agent_flow.core.memory_index import ensure_index_ready, search_index
from agent_flow.core.recall import RecallManager
from agent_flow.core.skill_manager import SkillManager


@dataclass
class RecommendedSkill:
    """A skill recommended for the current prompt based on trigger matching."""

    name: str
    why: str
    path: str


@dataclass
class MemoryHit:
    """A memory entry relevant to the current prompt."""

    entry_id: str
    title: str
    source_type: str
    confidence: float
    summary: str


@dataclass
class RecallHit:
    """A recall summary relevant to the current prompt."""

    summary_id: str
    task: str
    outcome: str
    confidence: float


@dataclass
class SkillTreeHit:
    """A skill-tree entry matching the current prompt."""

    skill_name: str
    task: str
    updated_at: str
    score: int


@dataclass
class RuntimeContext:
    """Unified runtime context collected for a prompt — skills, memory, recall, team."""

    prompt: str
    runtime_mode: str = ""
    event: str = ""
    current_phase: str = ""
    recommended_skills: list[RecommendedSkill] = field(default_factory=list)
    skill_tree_hits: list[SkillTreeHit] = field(default_factory=list)
    relevant_memory: list[MemoryHit] = field(default_factory=list)
    relevant_recall: list[RecallHit] = field(default_factory=list)
    frozen_memory_summary: str = ""
    skills_guidance_summary: str = ""
    agent_team_config: str = ""
    team_id: str = ""
    team_assigned_tasks: list[str] = field(default_factory=list)
    team_available_handoffs: list[str] = field(default_factory=list)


@dataclass
class ContextFingerprint:
    """Tracks what context was last injected to enable diff-based updates."""

    skill_names: list[str] = field(default_factory=list)
    skill_tree_ids: list[str] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)
    recall_ids: list[str] = field(default_factory=list)
    timestamp: float = 0.0
    current_phase: str = ""
    runtime_mode: str = ""


@dataclass
class ContextDiff:
    """The delta between current context and a previous fingerprint."""

    new_skills: list[RecommendedSkill] = field(default_factory=list)
    new_skill_tree: list[SkillTreeHit] = field(default_factory=list)
    new_memory: list[MemoryHit] = field(default_factory=list)
    new_recall: list[RecallHit] = field(default_factory=list)
    phase_changed: bool = False
    current_phase: str = ""
    runtime_mode_changed: bool = False
    runtime_mode: str = ""


# Path to the fingerprint file relative to .agent-flow/state/
_FINGERPRINT_FILENAME = "startup-context-fingerprint.json"
_TARGET_STATE_FILES: dict[str, str] = {
    "claude-hook": "startup-context.md",
    "executor-system": "executor-runtime-context.md",
    "doctor": "doctor-runtime-context.md",
}


def collect_runtime_context(
    project_dir: Path,
    prompt: str,
    *,
    runtime_mode: str = "",
    event: str = "",
) -> RuntimeContext:
    """Collect the unified runtime context for a prompt."""
    context = RuntimeContext(prompt=prompt.strip(), runtime_mode=runtime_mode or project_runtime_backend(project_dir))
    context.event = event
    context.current_phase = _load_current_phase(project_dir)
    context.skill_tree_hits = _find_skill_tree_hits(project_dir, prompt)
    context.recommended_skills = _find_recommended_skills(
        project_dir,
        prompt,
        skill_tree_hits=context.skill_tree_hits,
    )
    context.relevant_memory = _find_relevant_memory(project_dir, prompt)
    context.relevant_recall = _find_relevant_recall(project_dir, prompt)

    # Collect frozen memory summary (high-confidence Soul entries)
    try:
        from agent_flow.core.frozen_memory import FrozenMemoryManager
        frozen_mgr = FrozenMemoryManager(project_dir)
        snapshot = frozen_mgr.load_snapshot()
        context.frozen_memory_summary = frozen_mgr.format_for_system_prompt(snapshot)
    except Exception:
        pass  # Non-blocking: frozen memory is optional

    # Collect skills guidance (from executor prompts module)
    try:
        from agent_flow.executors.prompts import SKILLS_GUIDANCE
        context.skills_guidance_summary = SKILLS_GUIDANCE if SKILLS_GUIDANCE.strip() else ""
    except Exception:
        pass  # Non-blocking: skills guidance is optional

    # Collect agent team config summary
    try:
        from agent_flow.core.agent_team import AgentTeamConfig
        team_config = AgentTeamConfig.read(project_dir)
        if team_config and not team_config.is_solo():
            context.agent_team_config = team_config.injection_summary()
    except Exception:
        pass  # Non-blocking: agent team config is optional

    # Collect team context (team binding, assigned tasks, handoffs)
    try:
        from agent_flow.core.team import get_project_team_id, TeamConfig
        tid = get_project_team_id(project_dir)
        if tid:
            context.team_id = tid
            team_cfg = TeamConfig.read(tid)
            if team_cfg:
                context.team_assigned_tasks = _get_user_tasks(team_cfg)
                context.team_available_handoffs = _get_available_handoffs(team_cfg)
    except Exception:
        pass  # Non-blocking: team context is optional

    return context


def load_fingerprint(project_dir: Path) -> ContextFingerprint | None:
    """Load the last injected context fingerprint from disk."""
    fp_path = project_dir / ".agent-flow" / "state" / _FINGERPRINT_FILENAME
    if not fp_path.is_file():
        return None
    try:
        data = json.loads(fp_path.read_text(encoding="utf-8"))
        return ContextFingerprint(
            skill_names=data.get("skill_names", []),
            skill_tree_ids=data.get("skill_tree_ids", []),
            memory_ids=data.get("memory_ids", []),
            recall_ids=data.get("recall_ids", []),
            timestamp=float(data.get("timestamp", 0.0)),
            current_phase=data.get("current_phase", ""),
            runtime_mode=data.get("runtime_mode", ""),
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def save_fingerprint(project_dir: Path, context: RuntimeContext) -> None:
    """Persist the current context as a fingerprint for future diff comparison."""
    fp_path = project_dir / ".agent-flow" / "state" / _FINGERPRINT_FILENAME
    fp_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "skill_names": [s.name for s in context.recommended_skills],
        "skill_tree_ids": [item.skill_name for item in context.skill_tree_hits],
        "memory_ids": [m.entry_id for m in context.relevant_memory],
        "recall_ids": [r.summary_id for r in context.relevant_recall],
        "timestamp": time.time(),
        "current_phase": context.current_phase,
        "runtime_mode": context.runtime_mode,
    }
    fp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compute_context_diff(context: RuntimeContext, fingerprint: ContextFingerprint) -> ContextDiff:
    """Compute the delta between the current context and a previous fingerprint."""
    prev_skill_names = set(fingerprint.skill_names)
    prev_skill_tree_ids = set(fingerprint.skill_tree_ids)
    prev_memory_ids = set(fingerprint.memory_ids)
    prev_recall_ids = set(fingerprint.recall_ids)

    new_skills = [s for s in context.recommended_skills if s.name not in prev_skill_names]
    new_skill_tree = [s for s in context.skill_tree_hits if s.skill_name not in prev_skill_tree_ids]
    new_memory = [m for m in context.relevant_memory if m.entry_id not in prev_memory_ids]
    new_recall = [r for r in context.relevant_recall if r.summary_id not in prev_recall_ids]
    phase_changed = context.current_phase != fingerprint.current_phase
    mode_changed = context.runtime_mode != fingerprint.runtime_mode

    return ContextDiff(
        new_skills=new_skills,
        new_skill_tree=new_skill_tree,
        new_memory=new_memory,
        new_recall=new_recall,
        phase_changed=phase_changed,
        current_phase=context.current_phase if phase_changed else "",
        runtime_mode_changed=mode_changed,
        runtime_mode=context.runtime_mode if mode_changed else "",
    )


def render_runtime_context(
    project_dir: Path,
    context: RuntimeContext,
    *,
    target: str,
    diff_mode: bool = False,
) -> str:
    """Render runtime context for a specific consumer target."""
    if target == "claude-hook":
        return _render_claude_hook(project_dir, context, diff_mode=diff_mode)
    if target == "executor-system":
        return _render_executor_system(project_dir, context)
    if target == "doctor":
        return _render_doctor_summary(context)
    raise ValueError(f"Unsupported runtime context target: {target}")


def _render_claude_hook(project_dir: Path, context: RuntimeContext, *, diff_mode: bool = False) -> str:
    if diff_mode:
        fingerprint = load_fingerprint(project_dir)
        if fingerprint is not None:
            diff = compute_context_diff(context, fingerprint)
            rendered = _render_diff_reminder(diff)
            # Always persist the full context and update fingerprint
            full_lines: list[str] = ["<system-reminder>", "[startup-context]"]
            full_lines.extend(_render_common_fields(context))
            full_lines.append("</system-reminder>")
            _persist_runtime_context(project_dir, "\n".join(full_lines), target="claude-hook")
            save_fingerprint(project_dir, context)
            return rendered

    # Full context injection (no fingerprint or SessionStart)
    lines: list[str] = ["<system-reminder>", "[startup-context]"]
    lines.extend(_render_common_fields(context))
    lines.append("</system-reminder>")
    rendered = "\n".join(lines)
    _persist_runtime_context(project_dir, rendered, target="claude-hook")
    save_fingerprint(project_dir, context)
    return rendered


def _render_diff_reminder(diff: ContextDiff) -> str:
    """Render a compact diff-based reminder, or empty string if nothing changed."""
    if (
        not diff.new_skills
        and not diff.new_skill_tree
        and not diff.new_memory
        and not diff.new_recall
        and not diff.phase_changed
        and not diff.runtime_mode_changed
    ):
        return ""

    lines: list[str] = ["<system-reminder>", "[startup-context-diff]"]

    if diff.runtime_mode_changed:
        lines.append("runtime_mode:")
        lines.append(diff.runtime_mode)
        lines.append("")

    if diff.phase_changed:
        lines.append("current_phase:")
        lines.extend(diff.current_phase.splitlines())
        lines.append("")

    if diff.new_skills:
        lines.append("new_skills:")
        for skill in diff.new_skills[:5]:
            lines.append(f"- skill: {skill.name}")
            lines.append(f"  why: {skill.why}")
            lines.append(f"  path: {skill.path}")
        lines.append("")

    if diff.new_skill_tree:
        lines.append("new_skill_tree:")
        for item in diff.new_skill_tree[:5]:
            lines.append(f"- skill: {item.skill_name}")
            lines.append(f"  task: {item.task}")
            lines.append(f"  updated_at: {item.updated_at}")
            lines.append(f"  score: {item.score}")
        lines.append("")

    if diff.new_memory:
        lines.append("new_memory:")
        for memory in diff.new_memory[:4]:
            lines.append(f"- id: {memory.entry_id}")
            lines.append(f"  source: {memory.source_type}")
            lines.append(f"  confidence: {memory.confidence:.1f}")
            lines.append(f"  summary: {memory.summary}")
        lines.append("")

    if diff.new_recall:
        lines.append("new_recall:")
        for recall in diff.new_recall[:3]:
            lines.append(f"- id: {recall.summary_id}")
            lines.append(f"  outcome: {recall.outcome}")
            lines.append(f"  confidence: {recall.confidence:.1f}")
            lines.append(f"  task: {recall.task}")
        lines.append("")

    lines.append("</system-reminder>")
    return "\n".join(lines)


def _render_executor_system(project_dir: Path, context: RuntimeContext) -> str:
    lines: list[str] = ["[runtime-context]"]
    if context.runtime_mode:
        lines.append(f"runtime_mode: {context.runtime_mode}")
    if context.event:
        lines.append(f"event: {context.event}")
    if context.current_phase:
        lines.append("current_phase:")
        lines.extend(context.current_phase.splitlines())
        lines.append("")
    lines.extend(_render_list_sections(context))

    if context.frozen_memory_summary:
        lines.append("frozen_memory:")
        lines.append(context.frozen_memory_summary)
        lines.append("")

    if context.skills_guidance_summary:
        lines.append("skills_guidance:")
        lines.append(context.skills_guidance_summary)
        lines.append("")

    rendered = "\n".join(lines).strip()
    _persist_runtime_context(project_dir, rendered, target="executor-system")
    return rendered


def _render_doctor_summary(context: RuntimeContext) -> str:
    lines = [
        f"runtime_mode: {context.runtime_mode or 'unknown'}",
        f"event: {context.event or 'n/a'}",
        f"current_phase: {'present' if context.current_phase else 'missing'}",
        f"recommended_skills: {len(context.recommended_skills)}",
        f"relevant_memory: {len(context.relevant_memory)}",
        f"relevant_recall: {len(context.relevant_recall)}",
    ]
    return "\n".join(lines)


def _render_common_fields(context: RuntimeContext) -> list[str]:
    lines: list[str] = []
    if context.runtime_mode:
        lines.append("runtime_mode:")
        lines.append(context.runtime_mode)
        lines.append("")

    if context.event:
        lines.append("event:")
        lines.append(context.event)
        lines.append("")

    if context.current_phase:
        lines.append("current_phase:")
        lines.extend(context.current_phase.splitlines())
        lines.append("")

    lines.extend(_render_list_sections(context))

    if context.frozen_memory_summary:
        lines.append("frozen_memory:")
        lines.append(context.frozen_memory_summary)
        lines.append("")

    if context.skills_guidance_summary:
        lines.append("skills_guidance:")
        lines.append(context.skills_guidance_summary)
        lines.append("")

    if context.agent_team_config:
        lines.append("agent_team:")
        lines.append(context.agent_team_config)
        lines.append("")

    if context.team_id:
        lines.append("team_id:")
        lines.append(context.team_id)
        if context.team_assigned_tasks:
            lines.append(f"assigned_tasks: {context.team_assigned_tasks}")
        if context.team_available_handoffs:
            lines.append(f"available_handoffs: {context.team_available_handoffs}")
        lines.append("")

    return lines


def _render_list_sections(context: RuntimeContext) -> list[str]:
    lines: list[str] = []
    if context.recommended_skills:
        lines.append("recommended_skills:")
        for skill in context.recommended_skills[:5]:
            lines.append(f"- skill: {skill.name}")
            lines.append(f"  why: {skill.why}")
            lines.append(f"  path: {skill.path}")
        lines.append("")

    if context.skill_tree_hits:
        lines.append("skill_tree_hits:")
        for item in context.skill_tree_hits[:5]:
            lines.append(f"- skill: {item.skill_name}")
            lines.append(f"  task: {item.task}")
            lines.append(f"  updated_at: {item.updated_at}")
            lines.append(f"  score: {item.score}")
        lines.append("")

    if context.relevant_memory:
        lines.append("relevant_memory:")
        for memory in context.relevant_memory[:4]:
            lines.append(f"- id: {memory.entry_id}")
            lines.append(f"  source: {memory.source_type}")
            lines.append(f"  confidence: {memory.confidence:.1f}")
            lines.append(f"  summary: {memory.summary}")
        lines.append("")

    if context.relevant_recall:
        lines.append("relevant_recall:")
        for recall in context.relevant_recall[:3]:
            lines.append(f"- id: {recall.summary_id}")
            lines.append(f"  outcome: {recall.outcome}")
            lines.append(f"  confidence: {recall.confidence:.1f}")
            lines.append(f"  task: {recall.task}")
        lines.append("")
    return lines


def runtime_context_state_path(project_dir: Path, *, target: str) -> Path:
    """Return the file path for a persisted runtime context target."""
    state_dir = project_dir / ".agent-flow" / "state"
    filename = _TARGET_STATE_FILES.get(target)
    if filename is None:
        raise ValueError(f"Unsupported runtime context target: {target}")
    return state_dir / filename


def _persist_runtime_context(project_dir: Path, rendered: str, *, target: str) -> None:
    state_dir = project_dir / ".agent-flow" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    runtime_context_state_path(project_dir, target=target).write_text(rendered + "\n", encoding="utf-8")


def _load_current_phase(project_dir: Path) -> str:
    """Read the first few lines of current_phase.md for context injection."""
    phase_path = project_dir / ".agent-flow" / "state" / "current_phase.md"
    if not phase_path.is_file():
        return ""

    lines = [line.strip() for line in phase_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return "\n".join(lines[:6])


def _find_recommended_skills(
    project_dir: Path,
    prompt: str,
    *,
    skill_tree_hits: list[SkillTreeHit] | None = None,
) -> list[RecommendedSkill]:
    """Score and rank skills by trigger/keyword match against the prompt."""
    prompt_lower = prompt.lower()
    prompt_queries = _prompt_queries(prompt_lower)
    tree_hit_names = {hit.skill_name for hit in (skill_tree_hits or [])}
    matches: list[tuple[int, RecommendedSkill]] = []

    for scope in ("project", "global"):
        manager = SkillManager(project_dir, scope=scope)
        for spec in manager.list_skills():
            skill_path = manager.skills_dir / spec.name / "handler.md"
            score = _score_skill_match(
                skill_path,
                skill_name=spec.name,
                trigger=spec.trigger or "",
                prompt_queries=prompt_queries,
            )
            if score <= 0:
                continue
            if spec.name in tree_hit_names:
                score += 12

            matches.append(
                (
                    score,
                    RecommendedSkill(
                        name=spec.name,
                        why=f"matched trigger '{spec.trigger or spec.name}'",
                        path=str(skill_path),
                    ),
                )
            )

    matches.sort(key=lambda item: (-item[0], item[1].name))
    return [skill for _, skill in matches[:5]]


def _find_skill_tree_hits(project_dir: Path, prompt: str) -> list[SkillTreeHit]:
    """Search the skill-tree.json for entries matching the prompt."""
    path = project_dir / ".agent-flow" / "state" / "skill-tree.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        return []

    prompt_queries = _prompt_queries(prompt.lower())
    hits: list[SkillTreeHit] = []
    for item in skills:
        if not isinstance(item, dict):
            continue
        skill_name = str(item.get("name", "")).strip()
        task = str(item.get("task", "")).strip()
        updated_at = str(item.get("updated_at", "")).strip()
        steps = item.get("steps", [])
        if not skill_name:
            continue

        haystack_parts = [skill_name.lower(), task.lower()]
        if isinstance(steps, list):
            haystack_parts.extend(str(step).lower() for step in steps)
        haystack = " ".join(haystack_parts)

        score = 0
        for query in prompt_queries:
            if query and query in haystack:
                score += 1 if len(query) <= 4 else 3
        if score <= 0:
            continue

        hits.append(
            SkillTreeHit(
                skill_name=skill_name,
                task=_compact_text(task),
                updated_at=updated_at,
                score=score,
            )
        )
    hits.sort(key=lambda item: (-item.score, item.skill_name))
    return hits[:5]


def _score_skill_match(
    skill_path: Path,
    *,
    skill_name: str,
    trigger: str,
    prompt_queries: list[str],
) -> int:
    try:
        skill_blob = skill_path.read_text(encoding="utf-8").lower()
    except Exception:
        skill_blob = ""

    score = 0
    name_lower = skill_name.lower()
    trigger_lower = trigger.lower()
    for query in prompt_queries:
        if len(query) < 2:
            continue
        if query in trigger_lower:
            score += 6 if len(query) > 4 else 3
        if query in name_lower:
            score += 5 if len(query) > 4 else 2
        if skill_blob and query in skill_blob:
            score += 4 if len(query) > 4 else 1
    return score


def _find_relevant_memory(project_dir: Path, prompt: str) -> list[MemoryHit]:
    """Search memory index (FTS5) then Soul.md fallback for relevant entries."""
    db_path = _find_db_path(project_dir)
    if db_path:
        from agent_flow.core.memory_index import _MTIME_CACHE_FILENAME, _get_persisted_index_probe_ttl

        cache_path = str(Path(db_path).parent / _MTIME_CACHE_FILENAME)
        cache_fresh = False
        if Path(cache_path).is_file():
            try:
                import os as _os
                cache_age = time.time() - _os.path.getmtime(cache_path)
                if cache_age <= _get_persisted_index_probe_ttl():
                    cache_fresh = True
            except OSError:
                pass

        if cache_fresh:
            results = _search_memory_hits(db_path, prompt)
            hits = _hits_from_results(results)
            if hits:
                return hits
        else:
            try:
                ensure_index_ready(project_dir)
            except Exception:
                return []
            results = _search_memory_hits(db_path, prompt)
            hits = _hits_from_results(results)
            if hits:
                return hits
    else:
        try:
            ensure_index_ready(project_dir)
        except Exception:
            return []
        db_path = _find_db_path(project_dir)
        if db_path:
            results = _search_memory_hits(db_path, prompt)
            hits = _hits_from_results(results)
            if hits:
                return hits

    # Fallback: scan Soul.md directly (no DB hit needed)
    memory_dir = project_dir / ".agent-flow" / "memory" / "main"
    soul_path = memory_dir / "Soul.md"
    if soul_path.is_file():
        from agent_flow.core.memory import MemoryManager

        manager = MemoryManager(project_dir, "main")
        for entry in manager.read_soul().get("dynamic", []):
            haystack = " ".join(
                str(entry.get(key, "")) for key in ("module", "exp_type", "description")
            ).lower()
            if any(token in haystack for token in _prompt_tokens(prompt.lower())):
                hits.append(
                    MemoryHit(
                        entry_id=f"soul-{entry.get('date', '')}-{entry.get('module', '')}-{entry.get('exp_type', '')}",
                        title=entry.get("module", ""),
                        source_type="soul",
                        confidence=float(entry.get("confidence", 0.0) or 0.0),
                        summary=_compact_text(entry.get("description", "")),
                    )
                )
            if len(hits) >= 4:
                break
    return hits


def _hits_from_results(results: list[dict]) -> list[MemoryHit]:
    """Convert raw FTS5 search results into MemoryHit objects."""
    hits: list[MemoryHit] = []
    for item in results[:4]:
        hits.append(
            MemoryHit(
                entry_id=item.get("id", ""),
                title=item.get("title", ""),
                source_type=item.get("source_type", ""),
                confidence=float(item.get("confidence", 0.0) or 0.0),
                summary=_compact_text(item.get("content_summary", "") or item.get("title", "")),
            )
        )
    return hits


def _find_relevant_recall(project_dir: Path, prompt: str) -> list[RecallHit]:
    """Search recall index for session summaries relevant to the prompt."""
    manager = RecallManager(project_dir)
    results = manager.search_summaries(prompt, limit=3, use_fts5=True)
    if not results:
        for token in _prompt_tokens(prompt.lower()):
            results = manager.search_summaries(token, limit=3, use_fts5=True)
            if results:
                break
    hits = [
        RecallHit(
            summary_id=item.id,
            task=_compact_text(item.task_description),
            outcome=item.outcome or "unknown",
            confidence=item.confidence,
        )
        for item in results[:3]
    ]
    if hits:
        return hits

    for item in manager.get_recent_summaries(5):
        haystack = f"{item.task_description} {item.outcome}".lower()
        if any(token in haystack for token in _prompt_tokens(prompt.lower())):
            hits.append(
                RecallHit(
                    summary_id=item.id,
                    task=_compact_text(item.task_description),
                    outcome=item.outcome or "unknown",
                    confidence=item.confidence,
                )
            )
        if len(hits) >= 3:
            break
    return hits


def _prompt_tokens(prompt: str) -> list[str]:
    tokens: list[str] = []
    for keyword in _KEYWORD_BRIDGES:
        if keyword in prompt:
            tokens.append(keyword)
    for part in re.findall(r"[a-z0-9_-]+|[一-鿿]+", prompt.lower()):
        is_chinese = re.fullmatch(r"[一-鿿]+", part) is not None
        if len(part) >= 3 and (not is_chinese or len(part) <= 4):
            tokens.append(part)
        if is_chinese:
            for bigram in _chinese_bigrams(part):
                if len(part) <= 4 or bigram in _KEYWORD_BRIDGES:
                    tokens.append(bigram)
    for bigram in _chinese_bigrams(prompt.lower()):
        if bigram in _KEYWORD_BRIDGES:
            tokens.append(bigram)
    # Expand Chinese tokens via keyword bridges
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        bridge = _KEYWORD_BRIDGES.get(token)
        if bridge:
            expanded.extend(bridge.split())
    seen: set[str] = set()
    unique: list[str] = []
    for t in expanded:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:15]


def _prompt_queries(prompt: str) -> list[str]:
    clauses = [
        part.strip()
        for part in re.split(r"[\n\r,.;:!?()\[\]{}]+", prompt)
        if part.strip()
    ]
    queries: list[str] = []
    queries.extend(clauses[:8])
    queries.extend(_prompt_tokens(prompt))
    return list(dict.fromkeys(queries))


def _chinese_bigrams(text: str) -> list[str]:
    chinese_segments = re.findall(r"[一-鿿]+", text)
    bigrams: list[str] = []
    for segment in chinese_segments:
        for i in range(len(segment) - 1):
            bigrams.append(segment[i : i + 2])
    return bigrams


_KEYWORD_BRIDGES: dict[str, str] = {
    "飞书": "feishu lark",
    "文档": "doc document",
    "日历": "calendar",
    "任务": "task",
    "审查": "review",
    "测试": "test qa",
    "发布": "ship deploy",
    "发版": "release ship rollout",
    "上线": "release ship deploy",
    "优化": "optimize refactor",
    "修复": "fix bug",
    "稳住": "stabilize repair fix",
    "架构": "architecture",
}


def _search_memory_hits(db_path: str, prompt: str) -> list[dict]:
    for query in [prompt, *_prompt_tokens(prompt.lower())]:
        if not query.strip():
            continue
        try:
            results = search_index(db_path, query, limit=4)
        except Exception:
            continue
        if results:
            return results
    return []


def _find_db_path(project_dir: Path) -> str | None:
    for base in (".agent-flow", ".dev-workflow"):
        path = project_dir / base / "observations.db"
        if path.is_file():
            return str(path)
    return None


def _compact_text(text: str) -> str:
    """Collapse whitespace and truncate to 180 characters."""
    text = " ".join(text.split())
    return text[:180]


def _get_user_tasks(team_cfg: Any) -> list[str]:
    """Get task IDs assigned to the current user from the team task board."""
    try:
        task_board_path = team_cfg.state_dir() / "task-board.yaml"
        if not task_board_path.is_file():
            return []
        import yaml as _yaml
        data = _yaml.safe_load(task_board_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        tasks = data.get("tasks", [])
        if not isinstance(tasks, list):
            return []
        return [t["id"] for t in tasks if isinstance(t, dict) and t.get("status") == "in_progress"]
    except Exception:
        return []


def _get_available_handoffs(team_cfg: Any) -> list[str]:
    """Get IDs of available (unclaimed) handoff packets."""
    try:
        handoffs_dir = team_cfg.state_dir() / "handoffs"
        if not handoffs_dir.is_dir():
            return []
        result: list[str] = []
        for f in sorted(handoffs_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            if "status: active" in content[:500]:
                result.append(f.stem)
        return result[:5]
    except Exception:
        return []
