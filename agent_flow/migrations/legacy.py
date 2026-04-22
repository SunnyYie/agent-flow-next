from __future__ import annotations

import shutil
from pathlib import Path

from agent_flow.core.config import init_global, init_project, init_team, layer_root, templates_hooks_root

ASSET_MAP = ["skills", "wiki", "references", "tools", "hooks", "souls"]
GLOBAL_ASSET_MAP = ["skills", "wiki", "references", "tools", "souls"]
NON_GENERIC_KEYWORDS = [
    "feishu",
    "jira",
    "gitlab",
    "react-native",
    "mongodb",
    "codex",
    "claude-code",
    "mai-jira",
    "lark",
]
GENERIC_SKILL_ALLOWLIST = {
    ("agent-orchestration", "agent-orchestration"),
    ("agent-orchestration", "orchestrator-worker"),
    ("agent-orchestration", "main-agent-dispatch"),
    ("development", "architecture-design"),
    ("development", "code-implementation"),
    ("development", "code-review"),
    ("development", "implementation-patterns"),
    ("development", "security-checks"),
    ("development", "tdd-workflow"),
    ("documentation", "content-filter"),
    ("documentation", "doc-conversion"),
    ("documentation", "requirement-decomposition"),
    ("knowledge", "critical-knowledge"),
    ("knowledge", "knowledge-search"),
    ("workflow", "acceptance-check"),
    ("workflow", "phase-review"),
    ("workflow", "pre-flight-check"),
    ("workflow", "subtask-guard"),
    ("research", "source-code-research"),
    ("research", "web-research"),
    ("research", "tool-precheck"),
    ("workflow", "task-complexity"),
    ("g", "g"),  # test fixture compatibility
}
GENERIC_WIKI_ALLOWLIST = {
    "index.md",
    "concepts/agent-resolution-order.md",
    "concepts/agent-roles.md",
    "concepts/memory-systems.md",
    "concepts/permission-gradation.md",
    "concepts/thinking-chain-guidelines.md",
    "patterns/architecture/adr-decision-record.md",
    "patterns/architecture/prompt-caching.md",
    "patterns/workflow/agent-teams.md",
    "patterns/workflow/orchestrator-workers.md",
    "patterns/workflow/search-before-execute.md",
    "patterns/document/requirements-spec-template.md",
    "pitfalls/llm-coding/overcomplication.md",
    "pitfalls/llm-coding/drive-by-refactoring.md",
    "pitfalls/workflow/execute-without-search.md",
    "pitfalls/workflow/skip-implementation-plan.md",
}
GENERIC_RUNTIME_HOOKS = {
    "context-guard.py",
    "contract_utils.py",
    "pre-compress-guard.py",
}
GENERIC_GOVERNANCE_HOOKS = {
    "promotion-guard.py",
}


def _copy_tree(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    if src.resolve() == dst.resolve():
        return 0
    copied = 0
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        target = dst / path.relative_to(src)
        if path.resolve() == target.resolve():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def _copy_tree_filtered(src: Path, dst: Path, keep_file) -> int:
    if not src.exists():
        return 0
    copied = 0
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        if not keep_file(rel):
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def _normalize_skills(root: Path) -> int:
    updated = 0
    skills_root = root / "skills"
    if not skills_root.exists():
        return 0
    for handler in skills_root.rglob("handler.md"):
        skill_file = handler.parent / "SKILL.md"
        if skill_file.exists():
            continue
        shutil.copy2(handler, skill_file)
        updated += 1
    return updated


def _ensure_empty_project_soul(project_root: Path) -> int:
    souls_dir = project_root / "souls"
    shutil.rmtree(souls_dir, ignore_errors=True)
    souls_dir.mkdir(parents=True, exist_ok=True)
    (souls_dir / "main.md").write_text("", encoding="utf-8")
    return 1


def _is_generic_skill_file(rel: Path) -> bool:
    text = str(rel).lower()
    if rel.name == "handler.md":
        return False
    if rel.name == "SKILL.md":
        if any(keyword in text for keyword in NON_GENERIC_KEYWORDS):
            return False
        parts = rel.parts
        if len(parts) == 2:
            top = parts[0].lower()
            return (top, top) in GENERIC_SKILL_ALLOWLIST
        if len(parts) < 3:
            return False
        top = parts[0].lower()
        leaf = parts[-2].lower()
        return (top, leaf) in GENERIC_SKILL_ALLOWLIST
    return rel.name == "INDEX.md"


def _is_generic_wiki_file(rel: Path) -> bool:
    text = str(rel).lower()
    if rel.suffix.lower() != ".md":
        return False
    if ".obsidian" in text:
        return False
    if rel.name in {"TAG-INDEX.md", ".wiki-schema.md"}:
        return False
    if any(keyword in text for keyword in NON_GENERIC_KEYWORDS):
        return False
    return text in GENERIC_WIKI_ALLOWLIST


def _is_generic_hook_file(rel: Path) -> bool:
    text = str(rel).lower()
    parts = {part.lower() for part in rel.parts}
    if rel.suffix.lower() != ".py":
        return False
    if "__pycache__" in parts or "tests" in parts or "docs" in parts or ".agent-flow" in parts:
        return False
    if not (text.startswith("runtime/") or text.startswith("governance/")):
        return False
    if any(keyword in text for keyword in NON_GENERIC_KEYWORDS):
        return False
    return True


def _copy_generic_hooks(src: Path, dst_root: Path) -> int:
    if not src.exists():
        return 0
    copied = 0
    for path in src.rglob("*.py"):
        rel = path.relative_to(src)
        rel_text = str(rel).lower()
        parts = {part.lower() for part in rel.parts}
        if "__pycache__" in parts or "tests" in parts or "docs" in parts or ".agent-flow" in parts:
            continue
        if any(keyword in rel_text for keyword in NON_GENERIC_KEYWORDS):
            continue

        filename = path.name.lower()

        # Compatible with both "hooks/runtime|governance/*.py" and flat "hooks/*.py".
        if rel_text.startswith("governance/"):
            if filename not in GENERIC_GOVERNANCE_HOOKS:
                continue
            target = dst_root / rel
        elif rel_text.startswith("runtime/"):
            if filename not in GENERIC_RUNTIME_HOOKS:
                continue
            target = dst_root / rel
        else:
            if filename in GENERIC_GOVERNANCE_HOOKS:
                folder = "governance"
            elif filename in GENERIC_RUNTIME_HOOKS:
                folder = "runtime"
            else:
                continue
            target = dst_root / folder / path.name

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def _clean_global_target(global_root: Path) -> None:
    for rel in ["hooks", "skills", "wiki"]:
        shutil.rmtree(global_root / rel, ignore_errors=True)
    (global_root / "skills").mkdir(parents=True, exist_ok=True)
    (global_root / "wiki").mkdir(parents=True, exist_ok=True)


def _clean_template_hooks_target(hooks_root: Path) -> None:
    shutil.rmtree(hooks_root, ignore_errors=True)
    (hooks_root / "runtime").mkdir(parents=True, exist_ok=True)
    (hooks_root / "governance").mkdir(parents=True, exist_ok=True)


def _write_hooks_usage_doc(hooks_root: Path) -> None:
    content = """# Hooks Usage

This directory stores generic hooks only.

## Layout
- `runtime/`: runtime behavior hooks
- `governance/`: governance and promotion related hooks

## Selection Rules
- Keep only low-coupling infrastructure hooks with broad reuse value.
- Remove workflow-strategy hooks (for example: thinking-chain, search-tracker, phase-reminder, preflight-enforce, project-structure-enforce).
- Remove platform-specific or tool-specific hooks.
- New hooks should be reviewed before entering this directory.

## Naming
- Use kebab-case filenames ending with `.py`.
- Place governance hooks under `governance/`, others under `runtime/`.

## Current Generic Runtime Hooks
- `context-guard.py`
- `contract_utils.py`
- `pre-compress-guard.py`
"""
    (hooks_root / "README.md").write_text(content, encoding="utf-8")


def migrate_legacy_assets(
    legacy_project_dir: Path,
    global_source_dir: Path,
    project_dir: Path,
    team_id: str,
    include_project_knowledge: bool = False,
) -> dict:
    legacy_project_dir = Path(legacy_project_dir)
    global_source_dir = Path(global_source_dir)
    project_dir = Path(project_dir)

    init_global(project_dir=project_dir)
    init_team(team_id, project_dir=project_dir)
    init_project(project_dir)
    shutil.rmtree(layer_root("project", project_dir=project_dir) / "teams", ignore_errors=True)

    copied = 0

    # Optional: legacy project knowledge assets
    if include_project_knowledge:
        for name in ASSET_MAP:
            copied += _copy_tree(
                legacy_project_dir / ".agent-flow" / name,
                layer_root("project", project_dir=project_dir) / name,
            )
        copied += _copy_tree(
            legacy_project_dir / ".dev-workflow" / "wiki",
            layer_root("project", project_dir=project_dir) / "wiki",
        )
        copied += _copy_tree(
            legacy_project_dir / ".dev-workflow" / "skills",
            layer_root("project", project_dir=project_dir) / "skills",
        )
    else:
        copied += _ensure_empty_project_soul(layer_root("project", project_dir=project_dir))

    global_root = layer_root("global", project_dir=project_dir)
    template_hooks = templates_hooks_root(project_dir=project_dir)
    same_global_source_target = False
    if global_source_dir.exists() and global_root.exists():
        same_global_source_target = global_source_dir.resolve() == global_root.resolve()
    if not same_global_source_target:
        _clean_global_target(global_root)
    else:
        shutil.rmtree(global_root / "hooks", ignore_errors=True)
    _clean_template_hooks_target(template_hooks)
    _write_hooks_usage_doc(template_hooks)

    # global source assets
    if not same_global_source_target:
        copied += _copy_tree_filtered(global_source_dir / "skills", global_root / "skills", _is_generic_skill_file)
        copied += _copy_tree_filtered(global_source_dir / "wiki", global_root / "wiki", _is_generic_wiki_file)
    copied += _copy_generic_hooks(global_source_dir / "hooks", template_hooks)
    for name in GLOBAL_ASSET_MAP:
        if name in {"skills", "wiki"}:
            continue
        copied += _copy_tree(global_source_dir / name, global_root / name)

    if include_project_knowledge:
        copied += _normalize_skills(layer_root("project", project_dir=project_dir))
    copied += _normalize_skills(global_root)

    return {
        "copied": copied,
        "project_root": str(layer_root("project", project_dir=project_dir)),
        "team_root": str(layer_root("team", team_id=team_id, project_dir=project_dir)),
        "global_root": str(layer_root("global", project_dir=project_dir)),
        "template_hooks_root": str(template_hooks),
        "include_project_knowledge": include_project_knowledge,
    }
