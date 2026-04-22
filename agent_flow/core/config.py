from __future__ import annotations

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
    "hooks/runtime",
    "hooks/governance",
    "souls",
    "state",
]

def resources_root(project_dir: Path | None = None) -> Path:
    import os

    env = os.getenv("AGENT_FLOW_RESOURCES_ROOT")
    if env:
        return Path(env).expanduser()
    base = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    return base / "agent_flow" / "resources"


def templates_hooks_root(project_dir: Path | None = None) -> Path:
    base = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()
    return base / "agent_flow" / "templates" / "hooks"


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
    lines = [
        "# Team Skills Index",
        "",
        "This index is a high-level map of reusable global Agent-flow skills by scene.",
        f"Global skills root: `{skills_root}`",
        "",
        "## Scenes",
    ]

    if not scenes:
        lines.append("- No global skills found yet.")
        return "\n".join(lines) + "\n"

    for scene, count, samples in scenes:
        scene_path = skills_root / scene
        lines.append(f"- [{scene}]({scene_path}) ({count} skills)")
        for sample in samples:
            rel = sample.relative_to(skills_root)
            skill_name = rel.parts[-2] if len(rel.parts) >= 2 else rel.stem
            lines.append(f"  - [{skill_name}]({sample})")
    return "\n".join(lines) + "\n"


def _build_wiki_index(global_root: Path) -> str:
    wiki_root = global_root / "wiki"
    scenes = _wiki_scene_summary(wiki_root)
    lines = [
        "# Team Wiki Index",
        "",
        "This index is a high-level map of reusable global Agent-flow wiki knowledge by scene.",
        f"Global wiki root: `{wiki_root}`",
        "",
        "## Scenes",
    ]

    if not scenes:
        lines.append("- No global wiki docs found yet.")
        return "\n".join(lines) + "\n"

    for scene, count, samples in scenes:
        scene_path = wiki_root / scene
        lines.append(f"- [{scene}]({scene_path}) ({count} docs)")
        for sample in samples:
            rel = sample.relative_to(wiki_root)
            lines.append(f"  - [{rel}]({sample})")
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

- `hooks/`: 团队级 Hook（运行时与治理）
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
    (hooks_root / "runtime").mkdir(parents=True, exist_ok=True)
    (hooks_root / "governance").mkdir(parents=True, exist_ok=True)
    (root / "config.yaml").write_text(yaml.safe_dump(GlobalConfig().model_dump(), sort_keys=False), encoding="utf-8")
    return root


def init_team(team_id: str, name: str = "", project_dir: Path | None = None) -> Path:
    root = _ensure_layout(layer_root("team", team_id=team_id, project_dir=project_dir), TEAM_ASSET_DIRS)
    config = TeamConfig(team_id=team_id, name=name)
    (root / "team.yaml").write_text(yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")
    global_root = layer_root("global", project_dir=project_dir)
    _write_team_index_docs(team_root=root, global_root=global_root)
    _write_team_anchor_docs(team_root=root, global_root=global_root)
    _write_team_readme(team_root=root, team_id=team_id, team_name=name)
    return root


def init_team_flow(team_id: str, name: str = "", project_dir: Path | None = None) -> Path:
    return init_team(team_id=team_id, name=name, project_dir=project_dir)


def init_project(project_dir: Path) -> Path:
    root = _ensure_layout(layer_root("project", project_dir=project_dir), PROJECT_DEFAULT_DIRS)
    cfg = ProjectConfig(name=Path(project_dir).resolve().name)
    (root / "config.yaml").write_text(yaml.safe_dump(cfg.model_dump(), sort_keys=False), encoding="utf-8")
    soul_path = root / "souls" / "main.md"
    if not soul_path.exists():
        soul_path.write_text("", encoding="utf-8")
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
    return config_path


def project_team_id(project_dir: Path) -> str:
    config_path = layer_root("project", project_dir=project_dir) / "config.yaml"
    if not config_path.exists():
        return ""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return data.get("team_id", "")
