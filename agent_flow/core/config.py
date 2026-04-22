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
    "skills",
    "wiki",
    "references",
    "tools",
    "hooks/runtime",
    "hooks/governance",
    "souls",
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


def team_root_base() -> Path:
    import os

    env = os.getenv("AGENT_FLOW_TEAM_ROOT")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".agent-flow" / "teams"


def layer_root(layer: str, project_dir: Path | None = None, team_id: str | None = None) -> Path:
    if layer == "global":
        return resources_root(project_dir) / "global"
    if layer == "team":
        if not team_id:
            raise ValueError("team_id is required for team layer")
        return team_root_base() / team_id
    if layer == "project":
        if project_dir is None:
            raise ValueError("project_dir is required for project layer")
        return Path(project_dir) / ".agent-flow"
    raise ValueError(f"unknown layer: {layer}")


def _ensure_layout(root: Path, dirs: list[str]) -> Path:
    for rel in dirs:
        (root / rel).mkdir(parents=True, exist_ok=True)
    return root


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
    return root


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
