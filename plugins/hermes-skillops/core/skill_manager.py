"""Skill manager — CRUD operations and auto-creation for agent-flow skills.

Implements the hermes skill_manage concept: programmatic skill creation,
editing, patching, and deletion with YAML frontmatter + Markdown format.

Project-level skills live in ``.dev-workflow/skills/`` while ``.agent-flow``
keeps only mediator indexes. Global skills still live in ``~/.agent-flow``.
"""

from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agent_flow.core.config import project_primary_skills_dir


class SkillSpec(BaseModel):
    """Pydantic model for a skill's metadata (YAML frontmatter)."""

    name: str
    version: str = "1.0.0"
    trigger: str = ""
    applicable_agents: list[str] = Field(default_factory=lambda: ["main", "executor"])
    confidence: float = 0.8
    abstraction: str = "project"  # project | framework | universal
    created: str = ""
    updated: str = ""


class SkillManager:
    """CRUD operations for agent-flow skills — hermes skill_manage concept.

    Skills are stored as ``.dev-workflow/skills/{name}/handler.md`` for
    project scope, with YAML frontmatter metadata and Markdown body
    (Trigger, Procedure, Rules).
    """

    def __init__(self, project_dir: Path, scope: str = "project") -> None:
        if scope == "global":
            self.skills_dir = Path.home() / ".agent-flow" / "skills"
        elif scope == "team":
            from agent_flow.core.team import team_skills_dir
            ts = team_skills_dir(project_dir)
            if ts is None:
                raise ValueError("Project has no team binding; cannot use scope='team'")
            self.skills_dir = ts
        else:
            self.skills_dir = project_primary_skills_dir(project_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    # -- CRUD ----------------------------------------------------------------

    def create_skill(self, spec: SkillSpec, procedure: str, rules: str = "") -> Path:
        """Create a new skill from a spec, procedure text, and optional rules.

        Returns the path to the created handler.md.
        Raises FileExistsError if the skill already exists.
        """
        skill_dir = self.skills_dir / spec.name
        if skill_dir.is_dir() and (skill_dir / "handler.md").exists():
            raise FileExistsError(f"Skill '{spec.name}' already exists at {skill_dir}")

        now = datetime.now().strftime("%Y-%m-%d")
        spec.created = spec.created or now
        spec.updated = now

        content = _render_handler_md(spec, procedure, rules)
        skill_dir.mkdir(parents=True, exist_ok=True)
        handler_path = skill_dir / "handler.md"
        handler_path.write_text(content, encoding="utf-8")
        return handler_path

    def edit_skill(
        self,
        name: str,
        spec_patches: dict | None = None,
        procedure_patch: str | None = None,
        rules_patch: str | None = None,
    ) -> Path:
        """Edit an existing skill by applying patches to its spec and/or body.

        ``spec_patches`` is a dict of field→value to update in frontmatter.
        ``procedure_patch`` replaces the procedure text (not merge).
        ``rules_patch`` replaces the rules text (not merge).

        Returns the path to the modified handler.md.
        Raises FileNotFoundError if the skill doesn't exist.
        """
        handler_path = self.skills_dir / name / "handler.md"
        if not handler_path.is_file():
            raise FileNotFoundError(f"Skill '{name}' not found at {handler_path}")

        current = self.read_skill(name)
        spec = current["spec"]
        procedure = current["procedure"]
        rules = current["rules"]

        # Apply spec patches
        if spec_patches:
            for key, value in spec_patches.items():
                if hasattr(spec, key):
                    setattr(spec, key, value)

        spec.updated = datetime.now().strftime("%Y-%m-%d")

        # Apply body patches
        if procedure_patch is not None:
            procedure = procedure_patch
        if rules_patch is not None:
            rules = rules_patch

        content = _render_handler_md(spec, procedure, rules)
        handler_path.write_text(content, encoding="utf-8")
        return handler_path

    def patch_skill(self, name: str, field_patches: dict) -> Path:
        """Patch specific frontmatter fields of a skill.

        Convenience wrapper around edit_skill for frontmatter-only changes.
        ``field_patches`` is a dict like ``{"confidence": 0.9, "trigger": "new-trigger"}``.
        """
        return self.edit_skill(name, spec_patches=field_patches)

    def delete_skill(self, name: str) -> bool:
        """Delete a skill directory. Returns True if deleted, False if not found."""
        skill_dir = self.skills_dir / name
        if not skill_dir.is_dir():
            return False

        # Remove all files in the skill directory, then the directory itself
        for item in skill_dir.iterdir():
            item.unlink()
        skill_dir.rmdir()
        return True

    def list_skills(self, trigger_match: str | None = None) -> list[SkillSpec]:
        """List all skills, optionally filtered by trigger keyword match."""
        specs: list[SkillSpec] = []
        if not self.skills_dir.is_dir():
            return specs

        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            handler = skill_dir / "handler.md"
            if not handler.is_file():
                continue

            spec = _parse_frontmatter_to_spec(handler)
            if spec is None:
                continue

            if trigger_match is not None:
                if trigger_match.lower() not in spec.trigger.lower():
                    continue

            specs.append(spec)

        return specs

    def read_skill(self, name: str) -> dict:
        """Read a skill's full content: spec, procedure, rules.

        Returns dict with keys: spec (SkillSpec), procedure (str), rules (str).
        Raises FileNotFoundError if the skill doesn't exist.
        """
        handler_path = self.skills_dir / name / "handler.md"
        if not handler_path.is_file():
            raise FileNotFoundError(f"Skill '{name}' not found at {handler_path}")

        content = handler_path.read_text(encoding="utf-8")
        spec = _parse_frontmatter_to_spec(handler_path)
        if spec is None:
            spec = SkillSpec(name=name)

        procedure, rules = _parse_body_sections(content)
        return {"spec": spec, "procedure": procedure, "rules": rules}

    # -- Auto-creation -------------------------------------------------------

    def auto_create_from_experience(self, experience: dict, procedure: str) -> Path:
        """Auto-create a skill from a Soul.md experience entry.

        Used by organizer.promote_high_value() and runtime hooks.
        The skill name is derived from the experience module and type.
        """
        module = experience.get("module", "general")
        exp_type = experience.get("exp_type", "pattern")
        confidence = experience.get("confidence", 0.8)
        abstraction = experience.get("abstraction", "project")
        description = experience.get("description", "")

        # Generate a deterministic skill name from module + type
        name = f"{module}-{exp_type}"

        # If skill already exists, patch it instead of failing
        if (self.skills_dir / name / "handler.md").is_file():
            return self.edit_skill(
                name,
                spec_patches={
                    "confidence": max(confidence, self.read_skill(name)["spec"].confidence),
                    "updated": datetime.now().strftime("%Y-%m-%d"),
                },
                procedure_patch=procedure,
            )

        spec = SkillSpec(
            name=name,
            trigger=module,
            confidence=confidence,
            abstraction=abstraction,
        )
        rules = (
            f"此技能由经验自动生成 (module:{module}, type:{exp_type})\n"
            f"原经验: {description[:200]}"
        )
        return self.create_skill(spec, procedure, rules)


# ---------------------------------------------------------------------------
# Rendering and parsing helpers
# ---------------------------------------------------------------------------


def _render_handler_md(spec: SkillSpec, procedure: str, rules: str) -> str:
    """Render a SkillSpec + body into a handler.md string."""
    frontmatter = {
        "name": spec.name,
        "version": spec.version,
        "trigger": spec.trigger,
        "applicable_agents": spec.applicable_agents,
        "confidence": spec.confidence,
        "abstraction": spec.abstraction,
        "created": spec.created,
        "updated": spec.updated,
    }
    fm_str = yaml.dump(frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True).strip()

    parts = [
        f"---\n{fm_str}\n---",
        "",
        f"# Skill: {spec.name}",
        "",
        "## Trigger",
        f"当遇到与 {spec.trigger or spec.name} 相关的任务时触发" if spec.trigger else "（未指定触发条件）",
        "",
        "## Procedure",
        procedure or "（未指定操作步骤）",
        "",
        "## Rules",
        rules or "（无特殊约束）",
        "",
    ]
    return "\n".join(parts)


def _parse_frontmatter_to_spec(handler_path: Path) -> SkillSpec | None:
    """Parse YAML frontmatter from a handler.md into a SkillSpec."""
    try:
        content = handler_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return None

        end = content.find("---", 3)
        if end == -1:
            return None

        fm_str = content[3:end].strip()
        data = yaml.safe_load(fm_str)
        if not isinstance(data, dict):
            return None

        return SkillSpec(
            name=data.get("name", handler_path.parent.name),
            version=str(data.get("version", "1.0.0")),
            trigger=data.get("trigger", ""),
            applicable_agents=data.get("applicable_agents", ["main", "executor"]),
            confidence=float(data.get("confidence", 0.8)),
            abstraction=data.get("abstraction", "project"),
            created=str(data.get("created", "")),
            updated=str(data.get("updated", "")),
        )
    except Exception:
        return None


def _parse_body_sections(content: str) -> tuple[str, str]:
    """Parse Procedure and Rules sections from handler.md body.

    Returns (procedure_text, rules_text).
    """
    # Strip frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            body = content[end + 3:].strip()
        else:
            body = content
    else:
        body = content

    procedure = ""
    rules = ""

    lines = body.split("\n")
    current_section = None
    procedure_lines: list[str] = []
    rules_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped == "## Procedure":
            current_section = "procedure"
            continue
        elif stripped == "## Rules":
            current_section = "rules"
            continue
        elif stripped.startswith("## ") and current_section is not None:
            # New section ends the current one
            current_section = None
            continue

        if current_section == "procedure":
            procedure_lines.append(line)
        elif current_section == "rules":
            rules_lines.append(line)

    procedure = "\n".join(procedure_lines).strip()
    rules = "\n".join(rules_lines).strip()
    return procedure, rules
