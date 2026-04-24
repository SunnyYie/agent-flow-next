from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import yaml

from agent_flow.core.types import GlobalConfig, ProjectConfig, TeamConfig

GLOBAL_ASSET_DIRS = [
    "skills",
    "wiki",
    "references",
    "tools",
    "souls",
]

TEAM_ASSET_DIRS = [
    "hooks",
    "hooks/runtime",
    "hooks/governance",
    "references",
    "skills",
    "souls",
    "tools",
    "wiki",
]

PROJECT_DEFAULT_DIRS = [
    "hooks",
    "hooks/project",
    "hooks/project/runtime",
    "hooks/project/governance",
    "skills",
    "souls",
    "wiki",
    "state",
    "logs",
]


def bundled_resources_root() -> Path:
    return Path(__file__).resolve().parents[1] / "resources"

def resources_root(project_dir: Path | None = None) -> Path:
    import os

    env = os.getenv("AGENT_FLOW_RESOURCES_ROOT")
    if env:
        return Path(env).expanduser()
    base = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    return base / "agent_flow" / "resources"


def templates_hooks_root(project_dir: Path | None = None) -> Path:
    base = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    return base / "agent_flow" / "templates"


def bundled_templates_hooks_root() -> Path:
    return Path(__file__).resolve().parents[1] / "templates"


def team_root_base(project_dir: Path | None = None) -> Path:
    import os

    env = os.getenv("AGENT_FLOW_TEAM_ROOT")
    if env:
        return Path(env).expanduser()
    base = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    return base


def layer_root(layer: str, project_dir: Path | None = None, team_id: str | None = None) -> Path:
    if layer == "global":
        return resources_root(project_dir)
    if layer == "team":
        if not team_id:
            raise ValueError("team_id is required for team layer")
        return team_root_base(project_dir=project_dir) / team_id
    if layer == "project":
        if project_dir is None:
            raise ValueError("project_dir is required for project layer")
        return Path(project_dir) / ".agent-flow"
    raise ValueError(f"unknown layer: {layer}")


def _ensure_layout(root: Path, dirs: list[str]) -> Path:
    for rel in dirs:
        (root / rel).mkdir(parents=True, exist_ok=True)
    return root


def _has_files(root: Path) -> bool:
    if not root.exists():
        return False
    for p in root.rglob("*"):
        if p.is_file():
            return True
    return False


def _resolve_template_hooks_source(project_dir: Path | None = None) -> Path:
    primary = templates_hooks_root(project_dir=project_dir)
    if _has_files(primary / "global" / "hooks") or _has_files(primary / "team" / "hooks") or _has_files(primary / "project" / "hooks"):
        return primary

    bundled = bundled_templates_hooks_root()
    if _has_files(bundled / "global" / "hooks") or _has_files(bundled / "team" / "hooks") or _has_files(bundled / "project" / "hooks"):
        return bundled
    return primary


def _sync_template_hooks_layer(source_root: Path, target_root: Path, layer: str) -> None:
    source = source_root / layer / "hooks"
    if not source.exists():
        return

    target = target_root / layer
    target.mkdir(parents=True, exist_ok=True)

    for src in sorted(source.rglob("*"), key=lambda p: str(p).lower()):
        if not src.is_file():
            continue
        rel = src.relative_to(source)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Do not overwrite existing team hook files.
        if not dst.exists():
            shutil.copy2(src, dst)


def _sync_template_hooks_to_team(team_root: Path, project_dir: Path | None = None) -> None:
    source = _resolve_template_hooks_source(project_dir=project_dir)
    if not source.exists():
        return

    source_hooks = source / "team" / "hooks"
    if not source_hooks.exists():
        return

    target = team_root / "hooks"
    target.mkdir(parents=True, exist_ok=True)
    for src in sorted(source_hooks.rglob("*"), key=lambda p: str(p).lower()):
        if not src.is_file():
            continue
        rel = src.relative_to(source_hooks)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)


def _sync_template_hooks_to_project(project_root: Path, project_dir: Path | None = None) -> None:
    source = _resolve_template_hooks_source(project_dir=project_dir)
    if not source.exists():
        return

    source_hooks = source / "project" / "hooks"
    if not source_hooks.exists():
        return

    target = project_root / "hooks"
    target.mkdir(parents=True, exist_ok=True)
    for src in sorted(source_hooks.rglob("*"), key=lambda p: str(p).lower()):
        if not src.is_file():
            continue
        rel = src.relative_to(source_hooks)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)


def _prune_non_project_hook_scenes(project_root: Path) -> None:
    hooks_root = project_root / "hooks"
    for scene in ["global", "team", "project"]:
        shutil.rmtree(hooks_root / scene, ignore_errors=True)


def _prune_non_team_hook_scenes(team_root: Path) -> None:
    hooks_root = team_root / "hooks"
    for scene in ["global", "team", "project"]:
        shutil.rmtree(hooks_root / scene, ignore_errors=True)


def _resolve_global_asset_source(kind: str, global_root: Path) -> Path:
    primary = global_root / kind
    if _has_files(primary):
        return primary

    bundled = bundled_resources_root() / kind
    if _has_files(bundled):
        return bundled
    return primary


def _sync_global_asset_to_team(kind: str, team_root: Path, global_root: Path) -> None:
    source = _resolve_global_asset_source(kind=kind, global_root=global_root)
    if not source.exists():
        return

    target = team_root / kind
    target.mkdir(parents=True, exist_ok=True)

    for src in sorted(source.rglob("*"), key=lambda p: str(p).lower()):
        if not src.is_file():
            continue
        rel = src.relative_to(source)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Do not overwrite existing team asset files.
        if not dst.exists():
            shutil.copy2(src, dst)


def _skill_scene_summary(skills_root: Path) -> list[tuple[str, int, list[Path]]]:
    scenes: list[tuple[str, int, list[Path]]] = []
    if not skills_root.exists():
        return scenes

    for scene_dir in sorted((p for p in skills_root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        skills = sorted(scene_dir.rglob("SKILL.md"), key=lambda p: str(p.relative_to(skills_root)).lower())
        if not skills:
            continue
        scenes.append((scene_dir.name, len(skills), skills[:3]))
    return scenes


def _wiki_scene_summary(wiki_root: Path) -> list[tuple[str, int, list[Path]]]:
    scenes: list[tuple[str, int, list[Path]]] = []
    if not wiki_root.exists():
        return scenes

    ignored = {"index.md", "tag-index.md", ".wiki-schema.md"}
    for scene_dir in sorted((p for p in wiki_root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        docs = sorted(
            (
                p
                for p in scene_dir.rglob("*.md")
                if p.name.lower() not in ignored
            ),
            key=lambda p: str(p.relative_to(wiki_root)).lower(),
        )
        if not docs:
            continue
        scenes.append((scene_dir.name, len(docs), docs[:3]))
    return scenes


def _build_skills_index(global_root: Path) -> str:
    skills_root = global_root / "skills"
    scenes = _skill_scene_summary(skills_root)
    keys = _collect_global_skills(global_root)
    used_fallback = False

    if not scenes:
        bundled_root = bundled_resources_root()
        if bundled_root != global_root:
            bundled_skills = bundled_root / "skills"
            bundled_scenes = _skill_scene_summary(bundled_skills)
            if bundled_scenes:
                skills_root = bundled_skills
                scenes = bundled_scenes
                keys = _collect_global_skills(bundled_root)
                used_fallback = True

    scene_blurbs = {
        "workflow": "任务流程控制、复杂度评估、阶段门控与验收",
        "agent-orchestration": "多 Agent 编排、上下文预算与派发协议",
        "knowledge": "知识检索、经验晋升与关键知识固化",
        "development": "实现模式、TDD、审查与安全校验",
        "git": "分支协作与变更提交流程",
        "integration": "外部系统与平台集成流程",
        "ai-optimization": "提示词、缓存与 AI 工作流优化",
        "documentation": "文档转换、过滤与需求拆解",
        "python": "Python 工程模式与配置治理",
        "research": "源码/网络调研与工具前置检查",
    }

    def _first_match(prefix: str) -> str:
        for k in keys:
            if k.startswith(prefix):
                return k
        return ""

    lines = [
        "# Team Skills Index",
        "",
        "This index summarizes reusable Agent-flow skills for fast lookup.",
        f"Global skills root: `{skills_root}`",
    ]
    if used_fallback:
        lines.append("Source mode: bundled fallback (local global skills not found).")
    lines.extend([
        "",
        "## Quick Routing",
        "",
        f"- 任务入口与规划: `{_first_match('workflow/pre-flight-check') or 'workflow/*'}`",
        f"- 并行子 Agent 编排: `{_first_match('agent-orchestration/orchestrator-worker') or 'agent-orchestration/*'}`",
        f"- 知识先行检索: `{_first_match('knowledge/knowledge-search') or 'knowledge/*'}`",
        f"- 代码实现与测试: `{_first_match('development/code-implementation') or 'development/*'}`",
        f"- 交付前质量与验收: `{_first_match('workflow/acceptance-check') or 'workflow/*'}`",
        "",
        "## Implemented Skill Domains",
    ])

    if not scenes:
        lines.append("- No global skills found yet.")
        return "\n".join(lines) + "\n"

    for scene, count, _samples in scenes:
        lines.append(f"- `{scene}` ({count}): {scene_blurbs.get(scene, '通用技能集合')}")

    lines.extend([
        "",
        "## Scene Examples",
    ])

    for scene, _count, samples in scenes:
        sample_keys = []
        for sample in samples[:3]:
            rel = sample.relative_to(skills_root)
            sample_keys.append("/".join(rel.parts[:-1]))
        if sample_keys:
            joined = ", ".join(f"`{k}`" for k in sample_keys)
            lines.append(f"- `{scene}`: {joined}")

    lines.extend([
        "",
        "## Notes For Agents",
        "",
        "- 先按 domain 路由，再定位具体 skill。",
        "- 若多个 skill 同时适用，优先执行 workflow 相关 skill。",
        "- 新增团队技能后，建议更新本索引。",
    ])
    return "\n".join(lines) + "\n"


def _build_wiki_index(global_root: Path) -> str:
    wiki_root = global_root / "wiki"
    scenes = _wiki_scene_summary(wiki_root)
    docs = _collect_global_wiki(global_root)
    doc_set = set(docs)
    used_fallback = False

    if not scenes:
        bundled_root = bundled_resources_root()
        if bundled_root != global_root:
            bundled_wiki = bundled_root / "wiki"
            bundled_scenes = _wiki_scene_summary(bundled_wiki)
            if bundled_scenes:
                wiki_root = bundled_wiki
                scenes = bundled_scenes
                docs = _collect_global_wiki(bundled_root)
                doc_set = set(docs)
                used_fallback = True

    scene_blurbs = {
        "patterns": "可复用的成功实践与流程模板",
        "pitfalls": "已解决问题与常见踩坑记录",
        "concepts": "核心概念与原则定义",
        "decisions": "架构决策与治理规范",
        "tools": "工具使用手册与参数指南",
    }

    def _prefer(paths: list[str], fallback: str) -> str:
        for p in paths:
            if p in doc_set:
                return p
        return fallback

    lines = [
        "# Team Wiki Index",
        "",
        "This index summarizes reusable Agent-flow wiki knowledge for fast lookup.",
        f"Global wiki root: `{wiki_root}`",
    ]
    if used_fallback:
        lines.append("Source mode: bundled fallback (local global wiki not found).")
    lines.extend([
        "",
        "## Quick Routing",
        "",
        "- 流程模式检索: `" + _prefer(["patterns/workflow/search-before-execute.md"], "patterns/workflow/*") + "`",
        "- 架构与决策检索: `" + _prefer(["patterns/architecture/adr-decision-record.md"], "patterns/architecture/*") + "`",
        "- 故障与踩坑排查: `" + _prefer(["pitfalls/workflow/execute-without-search.md"], "pitfalls/*") + "`",
        "- 角色与记忆模型: `" + _prefer(["concepts/agent-roles.md", "concepts/memory-systems.md"], "concepts/*") + "`",
        "- 安全相关基线: `" + _prefer(["concepts/permission-gradation.md", "pitfalls/security/path-traversal-bypass.md"], "security/*") + "`",
        "",
        "## Solved Wiki Domains",
    ])

    if not scenes:
        lines.append("- No global wiki docs found yet.")
        return "\n".join(lines) + "\n"

    for scene, count, _samples in scenes:
        lines.append(f"- `{scene}` ({count}): {scene_blurbs.get(scene, '通用知识文档集合')}")

    lines.extend([
        "",
        "## Scene Examples",
    ])

    for scene, _count, samples in scenes:
        rel_paths = [str(sample.relative_to(wiki_root)) for sample in samples[:3]]
        if rel_paths:
            joined = ", ".join(f"`{p}`" for p in rel_paths)
            lines.append(f"- `{scene}`: {joined}")

    lines.extend([
        "",
        "## Notes For Agents",
        "",
        "- 先定位场景（patterns/pitfalls/concepts），再进入具体页面。",
        "- 大改动前先查 pitfalls，避免重复踩坑。",
        "- 新增团队经验时，优先归档到对应场景文档。",
    ])
    return "\n".join(lines) + "\n"


def _write_team_index_docs(team_root: Path, global_root: Path) -> None:
    (team_root / "skills" / "Index.md").write_text(_build_skills_index(global_root), encoding="utf-8")
    (team_root / "wiki" / "Index.md").write_text(_build_wiki_index(global_root), encoding="utf-8")


def _collect_global_skills(global_root: Path) -> list[str]:
    skills_root = global_root / "skills"
    if not skills_root.exists():
        return []
    keys: list[str] = []
    for p in sorted(skills_root.rglob("SKILL.md"), key=lambda x: str(x).lower()):
        rel = p.relative_to(skills_root)
        keys.append("/".join(rel.parts[:-1]))
    return keys


def _collect_global_wiki(global_root: Path) -> list[str]:
    wiki_root = global_root / "wiki"
    if not wiki_root.exists():
        return []
    ignored = {"index.md", "tag-index.md", ".wiki-schema.md"}
    keys: list[str] = []
    for p in sorted(wiki_root.rglob("*.md"), key=lambda x: str(x).lower()):
        if p.name.lower() in ignored:
            continue
        keys.append(str(p.relative_to(wiki_root)))
    return keys


def _collect_skill_keys_from_root(skills_root: Path | None) -> list[str]:
    if not skills_root or not skills_root.exists():
        return []
    keys: list[str] = []
    for p in sorted(skills_root.rglob("SKILL.md"), key=lambda x: str(x).lower()):
        rel = p.relative_to(skills_root)
        keys.append("/".join(rel.parts[:-1]))
    return keys


def _collect_wiki_docs_from_root(wiki_root: Path | None) -> list[str]:
    if not wiki_root or not wiki_root.exists():
        return []
    ignored = {"index.md", "tag-index.md", ".wiki-schema.md"}
    keys: list[str] = []
    for p in sorted(wiki_root.rglob("*.md"), key=lambda x: str(x).lower()):
        if p.name.lower() in ignored:
            continue
        keys.append(str(p.relative_to(wiki_root)))
    return keys


def _build_skills_anchor(global_root: Path) -> str:
    skills = _collect_global_skills(global_root)
    lines = [
        "# Skills Anchor",
        "",
        "团队可复用的全局技能锚点清单（简版）。",
        f"- Total global skills: {len(skills)}",
        "",
    ]
    if not skills:
        lines.append("- (empty)")
    else:
        for key in skills:
            lines.append(f"- {key}")
    lines.append("")
    return "\n".join(lines)


def _build_wiki_anchor(global_root: Path) -> str:
    wiki_docs = _collect_global_wiki(global_root)
    lines = [
        "# Wiki Anchor",
        "",
        "团队可复用的全局 wiki 锚点清单（简版）。",
        f"- Total global wiki docs: {len(wiki_docs)}",
        "",
    ]
    if not wiki_docs:
        lines.append("- (empty)")
    else:
        for key in wiki_docs:
            lines.append(f"- {key}")
    lines.append("")
    return "\n".join(lines)


def _write_team_anchor_docs(team_root: Path, global_root: Path) -> None:
    (team_root / "skills" / "ANCHOR.md").write_text(_build_skills_anchor(global_root), encoding="utf-8")
    (team_root / "wiki" / "ANCHOR.md").write_text(_build_wiki_anchor(global_root), encoding="utf-8")


def _write_team_readme(team_root: Path, team_id: str, team_name: str) -> None:
    display_name = team_name or team_id
    content = f"""# {display_name} Team Flow

本目录是团队级 Agent-flow 配置根目录，初始化后可直接被项目通过 `team_id: {team_id}` 绑定并复用。

## 如何使用

1. 在项目目录初始化并绑定团队：
   - `agent-flow init --project`
   - `agent-flow bind-team {team_id}`
2. 在项目内查看资源解析结果：
   - `agent-flow asset resolve`
   - `agent-flow asset list --layer team`
3. 在团队目录维护共享资产，项目会按 `project > team > global` 顺序解析。

## 目录说明

- `hooks/`: 团队级 Hook（按 `global/team/project` 通用程度拆分）
- `references/`: 团队共享参考资料
- `skills/`: 团队共享技能；`ANCHOR.md` 记录全局技能锚点
- `souls/`: 角色系统提示与职责定义
- `tools/`: 工具白名单与工具配置
- `wiki/`: 团队共享知识文档；`ANCHOR.md` 记录全局 wiki 锚点
- `team.yaml`: 团队元信息（team_id、名称、schema）

## 维护建议

- 新增团队技能：`agent-flow asset create --kind skills --name <scene>/<skill> --layer team --team-id {team_id}`
- 新增团队 wiki：`agent-flow asset create --kind wiki --name <scene>/<doc> --layer team --team-id {team_id}`
- 定期更新 `skills/ANCHOR.md` 与 `wiki/ANCHOR.md`（重新执行初始化或按需手动维护）。
"""
    (team_root / "README.md").write_text(content, encoding="utf-8")


def init_global(project_dir: Path | None = None) -> Path:
    root = _ensure_layout(layer_root("global", project_dir=project_dir), GLOBAL_ASSET_DIRS)
    hooks_root = templates_hooks_root(project_dir=project_dir)
    for scene in ["global", "team", "project"]:
        (hooks_root / scene / "hooks" / "runtime").mkdir(parents=True, exist_ok=True)
        (hooks_root / scene / "hooks" / "governance").mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text(yaml.safe_dump(GlobalConfig().model_dump(), sort_keys=False), encoding="utf-8")
    return root


def init_team(team_id: str, name: str = "", project_dir: Path | None = None) -> Path:
    root = _ensure_layout(layer_root("team", team_id=team_id, project_dir=project_dir), TEAM_ASSET_DIRS)
    _prune_non_team_hook_scenes(team_root=root)
    _sync_template_hooks_to_team(team_root=root, project_dir=project_dir)
    global_root = layer_root("global", project_dir=project_dir)
    _sync_global_asset_to_team(kind="references", team_root=root, global_root=global_root)
    _sync_global_asset_to_team(kind="souls", team_root=root, global_root=global_root)
    config = TeamConfig(team_id=team_id, name=name)
    (root / "team.yaml").write_text(yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")
    _write_team_index_docs(team_root=root, global_root=global_root)
    _write_team_anchor_docs(team_root=root, global_root=global_root)
    _write_team_readme(team_root=root, team_id=team_id, team_name=name)
    return root


def init_team_flow(team_id: str, name: str = "", project_dir: Path | None = None) -> Path:
    return init_team(team_id=team_id, name=name, project_dir=project_dir)


def _build_project_skills_index(project_root: Path, global_root: Path, team_root: Path | None = None) -> str:
    project_skills_root = project_root / "skills"
    team_skills_root = team_root / "skills" if team_root else None
    global_skills_root = global_root / "skills"

    project_scenes = _skill_scene_summary(project_skills_root)
    team_scenes = _skill_scene_summary(team_skills_root) if team_skills_root else []
    global_scenes = _skill_scene_summary(global_skills_root)

    project_keys = _collect_skill_keys_from_root(project_skills_root)
    team_keys = _collect_skill_keys_from_root(team_skills_root)
    global_keys = _collect_global_skills(global_root)

    used_fallback = False
    if not global_scenes:
        bundled_root = bundled_resources_root()
        if bundled_root != global_root:
            bundled_skills = bundled_root / "skills"
            bundled_scenes = _skill_scene_summary(bundled_skills)
            if bundled_scenes:
                global_skills_root = bundled_skills
                global_scenes = bundled_scenes
                global_keys = _collect_global_skills(bundled_root)
                used_fallback = True

    def _first_match(prefix: str) -> str:
        for keys in (project_keys, team_keys, global_keys):
            for k in keys:
                if k.startswith(prefix):
                    return k
        return ""

    lines = [
        "# Project Skills Index",
        "",
        "This index summarizes common/team/project Agent-flow skills for fast lookup.",
        f"Project skills root: `{project_skills_root}`",
        f"Team skills root: `{team_skills_root}`" if team_skills_root else "Team skills root: `(unbound)`",
        f"Global skills root: `{global_skills_root}`",
    ]
    if used_fallback:
        lines.append("Global source mode: bundled fallback (local global skills not found).")
    lines.extend([
        "",
        "## Quick Routing",
        "",
        f"- 任务入口与规划: `{_first_match('workflow/pre-flight-check') or 'workflow/*'}`",
        f"- 并行子 Agent 编排: `{_first_match('agent-orchestration/orchestrator-worker') or 'agent-orchestration/*'}`",
        f"- 知识先行检索: `{_first_match('knowledge/knowledge-search') or 'knowledge/*'}`",
        f"- 代码实现与测试: `{_first_match('development/code-implementation') or 'development/*'}`",
        f"- 交付前质量与验收: `{_first_match('workflow/acceptance-check') or 'workflow/*'}`",
        "",
        "## Common Skill Domains",
    ])

    if not global_scenes:
        lines.append("- No common skills found yet.")
    else:
        for scene, count, _samples in global_scenes:
            lines.append(f"- `{scene}` ({count}): 通用技能集合")

    lines.extend([
        "",
        "## Team Skill Domains",
    ])

    if not team_scenes:
        lines.append("- No team skills found yet.")
    else:
        for scene, count, _samples in team_scenes:
            lines.append(f"- `{scene}` ({count}): 团队共享技能集合")

    lines.extend([
        "",
        "## Project Skill Domains",
    ])

    if not project_scenes:
        lines.append("- No project skills found yet.")
    else:
        for scene, count, _samples in project_scenes:
            lines.append(f"- `{scene}` ({count}): 项目内自定义技能集合")

    lines.extend([
        "",
        "## Scene Examples",
    ])

    for scene, _count, samples in global_scenes:
        sample_keys: list[str] = []
        for sample in samples[:3]:
            rel = sample.relative_to(global_skills_root)
            sample_keys.append("/".join(rel.parts[:-1]))
        if sample_keys:
            joined = ", ".join(f"`{k}`" for k in sample_keys)
            lines.append(f"- common `{scene}`: {joined}")

    for scene, _count, samples in team_scenes:
        sample_keys: list[str] = []
        for sample in samples[:3]:
            rel = sample.relative_to(team_skills_root)  # type: ignore[arg-type]
            sample_keys.append("/".join(rel.parts[:-1]))
        if sample_keys:
            joined = ", ".join(f"`{k}`" for k in sample_keys)
            lines.append(f"- team `{scene}`: {joined}")

    for scene, _count, samples in project_scenes:
        sample_keys: list[str] = []
        for sample in samples[:3]:
            rel = sample.relative_to(project_skills_root)
            sample_keys.append("/".join(rel.parts[:-1]))
        if sample_keys:
            joined = ", ".join(f"`{k}`" for k in sample_keys)
            lines.append(f"- project `{scene}`: {joined}")

    lines.extend([
        "",
        "## Notes For Agents",
        "",
        "- Resolution priority: project > team > global.",
        "- Add project-specific workflows here.",
    ])
    return "\n".join(lines) + "\n"


def _build_project_wiki_index(project_root: Path, global_root: Path, team_root: Path | None = None) -> str:
    project_wiki_root = project_root / "wiki"
    team_wiki_root = team_root / "wiki" if team_root else None
    global_wiki_root = global_root / "wiki"

    project_scenes = _wiki_scene_summary(project_wiki_root)
    team_scenes = _wiki_scene_summary(team_wiki_root) if team_wiki_root else []
    global_scenes = _wiki_scene_summary(global_wiki_root)

    project_docs = set(_collect_wiki_docs_from_root(project_wiki_root))
    team_docs = set(_collect_wiki_docs_from_root(team_wiki_root))
    global_docs = set(_collect_global_wiki(global_root))

    used_fallback = False
    if not global_scenes:
        bundled_root = bundled_resources_root()
        if bundled_root != global_root:
            bundled_wiki = bundled_root / "wiki"
            bundled_scenes = _wiki_scene_summary(bundled_wiki)
            if bundled_scenes:
                global_wiki_root = bundled_wiki
                global_scenes = bundled_scenes
                global_docs = set(_collect_global_wiki(bundled_root))
                used_fallback = True

    def _prefer(paths: list[str], fallback: str) -> str:
        for docs in (project_docs, team_docs, global_docs):
            for p in paths:
                if p in docs:
                    return p
        return fallback

    lines = [
        "# Project Wiki Index",
        "",
        "This index summarizes common/team/project Agent-flow wiki knowledge for fast lookup.",
        f"Project wiki root: `{project_wiki_root}`",
        f"Team wiki root: `{team_wiki_root}`" if team_wiki_root else "Team wiki root: `(unbound)`",
        f"Global wiki root: `{global_wiki_root}`",
    ]
    if used_fallback:
        lines.append("Global source mode: bundled fallback (local global wiki not found).")
    lines.extend([
        "",
        "## Quick Routing",
        "",
        "- 流程模式检索: `" + _prefer(["patterns/workflow/search-before-execute.md"], "patterns/workflow/*") + "`",
        "- 架构与决策检索: `" + _prefer(["patterns/architecture/adr-decision-record.md"], "patterns/architecture/*") + "`",
        "- 故障与踩坑排查: `" + _prefer(["pitfalls/workflow/execute-without-search.md"], "pitfalls/*") + "`",
        "- 角色与记忆模型: `" + _prefer(["concepts/agent-roles.md", "concepts/memory-systems.md"], "concepts/*") + "`",
        "- 安全相关基线: `" + _prefer(["concepts/permission-gradation.md"], "security/*") + "`",
        "",
        "## Common Wiki Domains",
    ])

    if not global_scenes:
        lines.append("- No common wiki docs found yet.")
    else:
        for scene, count, _samples in global_scenes:
            lines.append(f"- `{scene}` ({count}): 通用知识文档集合")

    lines.extend([
        "",
        "## Team Wiki Domains",
    ])

    if not team_scenes:
        lines.append("- No team wiki docs found yet.")
    else:
        for scene, count, _samples in team_scenes:
            lines.append(f"- `{scene}` ({count}): 团队共享知识集合")

    lines.extend([
        "",
        "## Project Wiki Domains",
    ])

    if not project_scenes:
        lines.append("- No project wiki docs found yet.")
    else:
        for scene, count, _samples in project_scenes:
            lines.append(f"- `{scene}` ({count}): 项目内自定义知识集合")

    lines.extend([
        "",
        "## Scene Examples",
    ])

    for scene, _count, samples in global_scenes:
        rel_paths = [str(sample.relative_to(global_wiki_root)) for sample in samples[:3]]
        if rel_paths:
            joined = ", ".join(f"`{p}`" for p in rel_paths)
            lines.append(f"- common `{scene}`: {joined}")

    for scene, _count, samples in team_scenes:
        rel_paths = [str(sample.relative_to(team_wiki_root)) for sample in samples[:3]]  # type: ignore[arg-type]
        if rel_paths:
            joined = ", ".join(f"`{p}`" for p in rel_paths)
            lines.append(f"- team `{scene}`: {joined}")

    for scene, _count, samples in project_scenes:
        rel_paths = [str(sample.relative_to(project_wiki_root)) for sample in samples[:3]]
        if rel_paths:
            joined = ", ".join(f"`{p}`" for p in rel_paths)
            lines.append(f"- project `{scene}`: {joined}")

    lines.extend([
        "",
        "## Notes For Agents",
        "",
        "- Resolution priority: project > team > global.",
        "- Add project-specific pitfalls, patterns, and decisions here.",
    ])
    return "\n".join(lines) + "\n"


def _write_project_index_docs(project_root: Path, global_root: Path, team_root: Path | None = None) -> None:
    (project_root / "skills").mkdir(parents=True, exist_ok=True)
    (project_root / "wiki").mkdir(parents=True, exist_ok=True)
    (project_root / "skills" / "Index.md").write_text(
        _build_project_skills_index(project_root, global_root, team_root),
        encoding="utf-8",
    )
    (project_root / "wiki" / "Index.md").write_text(
        _build_project_wiki_index(project_root, global_root, team_root),
        encoding="utf-8",
    )


def _write_project_readme(project_root: Path, project_name: str) -> None:
    content = f"""# {project_name} — AgentFlow Project

本目录是项目级 Agent-flow 配置根目录，提供项目专属的 skills、wiki、hooks 等资产。

## 资源解析优先级

`project > team > global`

项目级资产会覆盖团队和全局的同名资产。

## 目录说明

- `hooks/`: 项目级 Hook（按 `global/team/project` 通用程度拆分）
- `references/`: 项目专属参考资料
- `skills/`: 项目专属技能；`Index.md` 为技能索引
- `souls/`: 项目专属角色定义
- `tools/`: 项目专属工具配置
- `wiki/`: 项目专属知识文档；`Index.md` 为知识索引
- `state/`: 执行状态与计划
- `logs/`: 开发日志

## 快速操作

- 查看资源解析：`agent-flow asset resolve`
- 创建项目技能：`agent-flow asset create --kind skills --name <name> --layer project`
- 创建项目 wiki：`agent-flow asset create --kind wiki --name <name> --layer project`
- 绑定团队：`agent-flow bind-team <team_id>`
"""
    (project_root / "README.md").write_text(content, encoding="utf-8")


def init_project(project_dir: Path) -> Path:
    root = _ensure_layout(layer_root("project", project_dir=project_dir), PROJECT_DEFAULT_DIRS)
    _prune_non_project_hook_scenes(project_root=root)
    existing_data = {}
    config_path = root / "config.yaml"
    if config_path.exists():
        existing_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    cfg = ProjectConfig(name=Path(project_dir).resolve().name, team_id=existing_data.get("team_id", ""))
    config_path.write_text(yaml.safe_dump(cfg.model_dump(), sort_keys=False), encoding="utf-8")
    _sync_template_hooks_to_project(project_root=root, project_dir=project_dir)
    soul_path = root / "souls" / "main.md"
    if not soul_path.exists():
        soul_path.write_text("", encoding="utf-8")
    global_root = layer_root("global", project_dir=project_dir)
    team_root = layer_root("team", team_id=cfg.team_id, project_dir=project_dir) if cfg.team_id else None
    _write_project_index_docs(root, global_root=global_root, team_root=team_root)
    _write_project_readme(root, cfg.name)
    return root


def bind_project_team(project_dir: Path, team_id: str) -> Path:
    root = layer_root("project", project_dir=project_dir)
    config_path = root / "config.yaml"
    data = {}
    if config_path.exists():
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    data["team_id"] = team_id
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    global_root = layer_root("global", project_dir=project_dir)
    team_root = layer_root("team", team_id=team_id, project_dir=project_dir)
    _write_project_index_docs(root, global_root=global_root, team_root=team_root)
    return config_path


def project_team_id(project_dir: Path) -> str:
    config_path = layer_root("project", project_dir=project_dir) / "config.yaml"
    if not config_path.exists():
        return ""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return data.get("team_id", "")


# ---------------------------------------------------------------------------
# Legacy-compatible helpers for migrated core modules
# ---------------------------------------------------------------------------

GLOBAL_DIR = Path.home() / ".agent-flow"
PROJECT_DIR_NAME = ".agent-flow"
DEV_WORKFLOW_DIR_NAME = ".dev-workflow"

DEFAULT_RECALL_INDEX = (
    "# Recall Index (Cross-session Summaries)\n\n"
    "## Recent Sessions\n"
    "| Date | Task | Outcome | ID |\n"
    "|------|------|---------|-----|\n"
)


def ensure_file(path: Path, content: str = "") -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return path


def _project_primary_wiki_dir(project_dir: Path) -> Path:
    dev_wiki = project_dir / DEV_WORKFLOW_DIR_NAME / "wiki"
    if dev_wiki.is_dir():
        return dev_wiki
    return project_dir / PROJECT_DIR_NAME / "wiki"


def _project_primary_skills_dir(project_dir: Path) -> Path:
    dev_skills = project_dir / DEV_WORKFLOW_DIR_NAME / "skills"
    if dev_skills.is_dir():
        return dev_skills
    return project_dir / PROJECT_DIR_NAME / "skills"


def project_primary_wiki_dir(project_dir: Path) -> Path:
    return _project_primary_wiki_dir(project_dir)


def project_primary_skills_dir(project_dir: Path) -> Path:
    return _project_primary_skills_dir(project_dir)


def _team_knowledge_dir(project_dir: Path) -> Path | None:
    team_id = project_team_id(project_dir)
    if not team_id:
        return None
    return layer_root("team", team_id=team_id, project_dir=project_dir)


def project_wiki_dirs(project_dir: Path, *, include_legacy: bool = True, include_team: bool = True) -> list[Path]:
    roots: list[Path] = []
    primary = _project_primary_wiki_dir(project_dir)
    if primary.is_dir():
        roots.append(primary)

    if include_team:
        team_root = _team_knowledge_dir(project_dir)
        if team_root:
            team_wiki = team_root / "wiki"
            if team_wiki.is_dir() and team_wiki not in roots:
                roots.append(team_wiki)

    if include_legacy:
        legacy = project_dir / PROJECT_DIR_NAME / "wiki"
        if legacy.is_dir() and legacy not in roots:
            roots.append(legacy)
    return roots


def project_skills_dirs(project_dir: Path, *, include_legacy: bool = True, include_team: bool = True) -> list[Path]:
    roots: list[Path] = []
    primary = _project_primary_skills_dir(project_dir)
    if primary.is_dir():
        roots.append(primary)

    if include_team:
        team_root = _team_knowledge_dir(project_dir)
        if team_root:
            team_skills = team_root / "skills"
            if team_skills.is_dir() and team_skills not in roots:
                roots.append(team_skills)

    if include_legacy:
        for legacy in [project_dir / PROJECT_DIR_NAME / "skills", project_dir / DEV_WORKFLOW_DIR_NAME / "skills"]:
            if legacy.is_dir() and legacy not in roots:
                roots.append(legacy)
    return roots


# ---------------------------------------------------------------------------
# Runtime configuration helpers
# ---------------------------------------------------------------------------

PROJECT_CONFIG_NAME = "config.yaml"

CLAUDE_PROJECT_COMMANDS = (
    "plan-review",
    "plan-eng-review",
    "run",
    "review",
    "qa",
    "ship",
)


def project_execution_commands(project_dir: Path) -> dict[str, list[str]]:
    """Return configured executor/verifier commands for the project."""
    config_path = project_dir / PROJECT_DIR_NAME / PROJECT_CONFIG_NAME
    if not config_path.is_file():
        return _maybe_add_builtin_executor({}, project_dir)

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return _maybe_add_builtin_executor({}, project_dir)

    execution = data.get("execution")
    if not isinstance(execution, dict):
        return _maybe_add_builtin_executor({}, project_dir)

    commands: dict[str, list[str]] = {}
    for key in ("executor_command", "verifier_command"):
        value = execution.get(key)
        if isinstance(value, list) and value and all(isinstance(part, str) for part in value):
            commands[key] = value
    return _maybe_add_builtin_executor(commands, project_dir)


def project_native_executor_command(project_dir: Path) -> list[str]:
    """Return an explicitly configured native executor bridge command, if any."""
    config_path = project_dir / PROJECT_DIR_NAME / PROJECT_CONFIG_NAME
    if not config_path.is_file():
        return []

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []

    execution = data.get("execution")
    if not isinstance(execution, dict):
        return []

    value = execution.get("native_executor_command")
    if isinstance(value, list) and value and all(isinstance(part, str) for part in value):
        return value
    return []


def project_native_executor(project_dir: Path) -> str:
    """Return the configured native executor shortcut, if any."""
    config_path = project_dir / PROJECT_DIR_NAME / PROJECT_CONFIG_NAME
    if not config_path.is_file():
        return ""

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""

    execution = data.get("execution")
    if not isinstance(execution, dict):
        return ""

    value = execution.get("native_executor")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def project_runtime_backend(project_dir: Path) -> str:
    """Return the configured runtime backend for auto-run stages."""
    config_path = project_dir / PROJECT_DIR_NAME / PROJECT_CONFIG_NAME
    if config_path.is_file():
        try:
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}

        execution = data.get("execution")
        if isinstance(execution, dict):
            value = execution.get("runtime_backend")
            if isinstance(value, str) and value.strip():
                return value.strip()

    if _should_default_to_claude_native(project_dir):
        return "claude-native"

    return "command"


def project_prefers_claude_native(project_dir: Path) -> bool:
    """Return True when the project explicitly prefers Claude Code native runtime."""
    return project_runtime_backend(project_dir) == "claude-native"


def project_runtime_backends(project_dir: Path) -> set[str]:
    """Return the configured runtime backends as a normalized set."""
    raw_value = project_runtime_backend(project_dir)
    separators = ["+", ",", " "]
    values = [raw_value]
    for separator in separators:
        expanded: list[str] = []
        for value in values:
            expanded.extend(value.split(separator))
        values = expanded

    normalized = {value.strip() for value in values if value.strip()}
    return normalized or {"command"}


def _maybe_add_builtin_executor(
    commands: dict[str, list[str]],
    project_dir: Path,
) -> dict[str, list[str]]:
    """Auto-populate executor_command from LLM config when not explicitly set."""
    if "executor_command" in commands:
        return commands

    if project_prefers_claude_native(project_dir):
        return commands

    if _auto_detect_disabled(project_dir):
        return commands

    try:
        from agent_flow.executors.llm_config import resolve_llm_config

        llm_config = resolve_llm_config(project_dir)
        if llm_config is not None and llm_config.is_valid:
            commands["executor_command"] = _builtin_executor_command()
    except Exception:
        pass

    return commands


def _auto_detect_disabled(project_dir: Path) -> bool:
    """Return True when ``execution.auto_detect_llm`` is explicitly set to false."""
    config_path = project_dir / PROJECT_DIR_NAME / PROJECT_CONFIG_NAME
    if not config_path.is_file():
        return False

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False

    execution = data.get("execution")
    if not isinstance(execution, dict):
        return False

    return execution.get("auto_detect_llm") is False


def _builtin_executor_command() -> list[str]:
    """Return the subprocess args for the built-in Anthropic executor."""
    return [sys.executable, "-m", "agent_flow.executors.anthropic_executor"]


def _should_default_to_claude_native(project_dir: Path) -> bool:
    """Detect whether the project should default to claude-native runtime."""
    if os.environ.get("CLAUDE_CODE") == "1":
        return True

    commands_dir = project_dir / ".claude" / "commands"
    if commands_dir.is_dir():
        for cmd_file in commands_dir.iterdir():
            if cmd_file.suffix in (".md", ".txt") and "agent-flow" in cmd_file.name.lower():
                return True

    for settings_path in (
        project_dir / ".claude" / "settings.json",
        project_dir / ".claude" / "settings.local.json",
    ):
        if not settings_path.is_file():
            continue
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = data.get("hooks", {})
            if isinstance(hooks, dict) and hooks:
                for _hook_type, hook_list in hooks.items():
                    if not isinstance(hook_list, list):
                        continue
                    for entry in hook_list:
                        try:
                            command = entry["hooks"][0]["command"]
                            if "agent-flow" in command or "agent_flow" in command:
                                return True
                        except (KeyError, IndexError, TypeError):
                            continue
        except (json.JSONDecodeError, OSError):
            continue

    return False
