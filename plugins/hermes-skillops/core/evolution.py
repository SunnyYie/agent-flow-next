"""Self-evolution helpers for crystallized skills, stagnation detection, and GEP prompts."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agent_flow.core.memory import MemoryManager
from agent_flow.core.skill_manager import SkillManager, SkillSpec

_MEMORY_PREFIX_RE = re.compile(r"^\[[^\]]+\]\s*")
_TAG_RE = re.compile(r"^\[(?P<tag>[A-Z_-]+)\]\s*")
_NON_WORD_RE = re.compile(r"[^\w\u4e00-\u9fff-]+", re.UNICODE)

_STRATEGY_WEIGHTS: dict[str, dict[str, int]] = {
    "balanced": {"innovate": 50, "optimize": 30, "repair": 20},
    "innovate": {"innovate": 80, "optimize": 15, "repair": 5},
    "harden": {"innovate": 20, "optimize": 40, "repair": 40},
    "repair-only": {"innovate": 0, "optimize": 20, "repair": 80},
}


@dataclass
class CrystallizedSkill:
    created: bool
    skill_name: str = ""
    skill_path: Path | None = None
    steps: list[str] | None = None
    validation_command: str = ""
    invalidations: list[str] | None = None


@dataclass
class StagnationPattern:
    signature: str
    occurrences: int
    should_interrupt: bool


class EvolutionEngine:
    """Build reusable assets from execution traces."""

    def __init__(self, project_dir: Path, agent_name: str = "main") -> None:
        self.project_dir = project_dir
        self.agent_name = agent_name
        self.memory = MemoryManager(project_dir, agent_name)
        self.skill_manager = SkillManager(project_dir)

    def crystallize_from_memory(self, task_description: str) -> CrystallizedSkill:
        """Extract a stable success path from Memory.md and save it as a skill."""
        memory_text = self.memory.read_memory()
        steps = self._extract_success_path(memory_text)
        if not steps:
            return CrystallizedSkill(created=False, steps=[])

        skill_name = self._skill_name_for_task(task_description)
        validation_checks = self._extract_validation_checks(memory_text)
        validation_command = "agent-flow run --dry-run"
        invalidations = self._build_invalidation_conditions(steps)
        procedure = "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps, start=1))
        rules = self._build_rules_text(validation_command, validation_checks, invalidations)
        spec = SkillSpec(
            name=skill_name,
            trigger=task_description,
            confidence=0.85,
            abstraction="project",
        )

        handler_path = self._upsert_skill(spec, procedure, rules)
        self._update_skill_tree(
            task_description,
            skill_name,
            steps,
            validation_command=validation_command,
            validation_checks=validation_checks,
            invalidations=invalidations,
        )
        self._record_skill_experience(task_description, skill_name, steps)
        return CrystallizedSkill(
            created=True,
            skill_name=skill_name,
            skill_path=handler_path,
            steps=steps,
            validation_command=validation_command,
            invalidations=invalidations,
        )

    def detect_stagnation(
        self,
        *,
        minimum_occurrences: int = 3,
        signature: str | None = None,
    ) -> StagnationPattern | None:
        """Detect repeated failure signatures that indicate an ineffective loop."""
        signatures: list[str] = []
        for line in self._clean_memory_lines(self.memory.read_memory()):
            tag, body = self._split_tag(line)
            if tag in {"ERROR", "FAIL", "FAILED"} and body:
                signatures.append(body)

        if not signatures:
            return None

        if signature is not None:
            occurrences = sum(1 for item in signatures if item == signature)
            if occurrences == 0:
                return None
            return StagnationPattern(
                signature=signature,
                occurrences=occurrences,
                should_interrupt=occurrences >= minimum_occurrences,
            )

        signature, occurrences = Counter(signatures).most_common(1)[0]
        return StagnationPattern(
            signature=signature,
            occurrences=occurrences,
            should_interrupt=occurrences >= minimum_occurrences,
        )

    def build_gep_prompt(
        self,
        task_description: str,
        *,
        strategy: str = "balanced",
        signals: list[str] | None = None,
    ) -> str:
        """Generate a tightly constrained GEP protocol prompt."""
        chosen = strategy if strategy in _STRATEGY_WEIGHTS else "balanced"
        weights = _STRATEGY_WEIGHTS[chosen]
        normalized_signals = signals or ["无额外 signals，按默认日志演化"]
        signal_lines = "\n".join(f"- {item}" for item in normalized_signals)
        return (
            "你现在进入严格 GEP 演化模式。\n"
            f"EVOLVE_STRATEGY={chosen}\n"
            f"任务: {task_description}\n"
            "禁止自由发散、禁止跳过证据、禁止输出无依据的新能力设想。\n"
            f"预算分配: 创新 {weights['innovate']}% / 优化 {weights['optimize']}% / 修复 {weights['repair']}%\n"
            "输入 signals:\n"
            f"{signal_lines}\n"
            "执行约束:\n"
            "1. 只能基于已有日志、记忆、技能和可验证信号提出演化动作。\n"
            "2. 优先复用已存在能力；只有证据不足时才允许新增技能或步骤。\n"
            "3. 如果检测到重复失败或停滞模式，必须先提出中断与去重方案，再讨论修复动作。\n"
            "4. 每个建议必须给出验证方法、回滚条件、影响范围。\n"
            "输出必须包含:\n"
            "- MutationIntent\n"
            "- Evidence\n"
            "- PlannedChanges\n"
            "- Validation\n"
            "- Rollback\n"
        )

    def _extract_success_path(self, memory_text: str) -> list[str]:
        lines = self._clean_memory_lines(memory_text)
        success_index = max(
            (idx for idx, line in enumerate(lines) if self._split_tag(line)[0] in {"SUCCESS", "DONE"}),
            default=len(lines),
        )
        candidate_lines = lines[: success_index + 1]
        steps: list[str] = []
        seen: set[str] = set()

        for line in candidate_lines:
            tag, body = self._split_tag(line)
            if tag not in {"TASK", "EXECUTE", "VERIFY", "SUCCESS"}:
                continue
            if tag == "TASK":
                continue
            normalized = body.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            steps.append(normalized)

        return steps

    def _upsert_skill(self, spec: SkillSpec, procedure: str, rules: str) -> Path:
        handler = self.skill_manager.skills_dir / spec.name / "handler.md"
        if handler.is_file():
            return self.skill_manager.edit_skill(
                spec.name,
                spec_patches={
                    "trigger": spec.trigger,
                    "confidence": spec.confidence,
                    "abstraction": spec.abstraction,
                },
                procedure_patch=procedure,
                rules_patch=rules,
            )
        return self.skill_manager.create_skill(spec, procedure, rules)

    def _update_skill_tree(
        self,
        task_description: str,
        skill_name: str,
        steps: list[str],
        *,
        validation_command: str,
        validation_checks: list[str],
        invalidations: list[str],
    ) -> None:
        state_dir = self.project_dir / ".agent-flow" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        index_path = state_dir / "skill-tree.json"
        existing: dict[str, object]
        if index_path.is_file():
            try:
                existing = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {"skills": []}
        else:
            existing = {"skills": []}

        skills = existing.get("skills", [])
        if not isinstance(skills, list):
            skills = []
        filtered = [item for item in skills if isinstance(item, dict) and item.get("name") != skill_name]
        filtered.append(
            {
                "name": skill_name,
                "task": task_description,
                "steps": steps,
                "validation": {
                    "command": validation_command,
                    "checks": validation_checks,
                },
                "invalidations": invalidations,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        index_path.write_text(
            json.dumps({"skills": filtered}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _record_skill_experience(self, task_description: str, skill_name: str, steps: list[str]) -> None:
        description = (
            f"结晶技能 {skill_name}，适用于任务“{task_description}”。"
            f"稳定路径: {' -> '.join(steps[:5])}"
        )
        self.memory.add_experience(
            date=datetime.now().strftime("%Y-%m-%d"),
            module="evolution",
            exp_type="skill-crystallization",
            description=description,
            confidence=0.85,
            abstraction="project",
        )

    def _skill_name_for_task(self, task_description: str) -> str:
        slug = _NON_WORD_RE.sub("-", task_description.strip()).strip("-") or "task"
        return f"task-{slug}"

    @staticmethod
    def _extract_validation_checks(memory_text: str) -> list[str]:
        checks: list[str] = []
        for line in EvolutionEngine._clean_memory_lines(memory_text):
            tag, body = EvolutionEngine._split_tag(line)
            if tag != "VERIFY":
                continue
            body = body.strip()
            if body and body not in checks:
                checks.append(body)
        if checks:
            return checks[:3]
        return ["关键流程验证通过"]

    @staticmethod
    def _build_invalidation_conditions(steps: list[str]) -> list[str]:
        key_step = steps[0] if steps else "关键前置步骤"
        return [
            f"关键前置步骤“{key_step}”不可执行或行为变化",
            "同一失败信号重复出现 3 次及以上",
            "验证检查项连续失败",
        ]

    @staticmethod
    def _build_rules_text(validation_command: str, checks: list[str], invalidations: list[str]) -> str:
        lines = [
            "仅保留最终验证通过的稳定路径；如果环境发生变化，先复核关键前置条件，再局部探索。",
            "",
            "Validation Command:",
            f"- {validation_command}",
            "Validation Checks:",
        ]
        lines.extend(f"- {check}" for check in checks)
        lines.append("Invalidation Conditions:")
        lines.extend(f"- {item}" for item in invalidations)
        return "\n".join(lines)

    @staticmethod
    def _clean_memory_lines(memory_text: str) -> list[str]:
        cleaned: list[str] = []
        for raw in memory_text.splitlines():
            stripped = _MEMORY_PREFIX_RE.sub("", raw).strip()
            if stripped:
                cleaned.append(stripped)
        return cleaned

    @staticmethod
    def _split_tag(line: str) -> tuple[str, str]:
        match = _TAG_RE.match(line)
        if not match:
            return "", line.strip()
        tag = match.group("tag").strip()
        body = line[match.end():].strip()
        return tag, body


def export_skill_tree(project_dir: Path) -> list[dict]:
    """Return the current crystallized skill tree for diagnostics/tests."""
    index_path = project_dir / ".agent-flow" / "state" / "skill-tree.json"
    if not index_path.is_file():
        return []
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    skills = payload.get("skills", [])
    if not isinstance(skills, list):
        return []
    return [item for item in skills if isinstance(item, dict)]
