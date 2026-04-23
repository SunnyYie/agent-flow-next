"""Team — Team identity, membership, and coordination models.

Manages team configuration for multi-user collaboration:
  - Team identity (team.yaml)
  - Membership and roles (admin / maintainer / member)
  - Knowledge sharing policies
  - Project-to-team binding

Team data lives in ``~/.agent-flow/teams/{team-id}/`` and is independent
of the existing single-user ``~/.agent-flow/`` structure.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ── Constants ──────────────────────────────────────────────────

TEAMS_DIR = Path.home() / ".agent-flow" / "teams"
TEAM_CONFIG_FILENAME = "team.yaml"

ROLE_ADMIN = "admin"
ROLE_MAINTAINER = "maintainer"
ROLE_MEMBER = "member"

ROLE_HIERARCHY: dict[str, int] = {
    ROLE_MEMBER: 0,
    ROLE_MAINTAINER: 1,
    ROLE_ADMIN: 2,
}


# ── Models ─────────────────────────────────────────────────────


class TeamMember(BaseModel):
    """A member of a team."""

    user_id: str
    display_name: str = ""
    role: str = ROLE_MEMBER
    joined: str = ""


class TeamPolicy(BaseModel):
    """Team-wide governance policies."""

    skill_approval: str = ROLE_MEMBER  # none | member | maintainer | admin
    wiki_edit: str = ROLE_MEMBER
    hook_install: str = ROLE_ADMIN
    knowledge_promotion: str = ROLE_MAINTAINER
    code_review_required: bool = False


class KnowledgeRepo(BaseModel):
    """Configuration for the team knowledge Git repository."""

    type: str = "none"  # git | local | none
    url: str = ""
    branch: str = "main"


class ProjectTeamBinding(BaseModel):
    """Project-level team binding stored in .agent-flow/config.yaml."""

    team_id: str = ""
    shared_resources: dict[str, bool] = Field(
        default_factory=lambda: {"skills": True, "wiki": True, "hooks": False}
    )
    sync: dict[str, Any] = Field(
        default_factory=lambda: {"auto_pull": True, "push_policy": "manual"}
    )


class TeamConfig(BaseModel):
    """Full team configuration stored in ~/.agent-flow/teams/{team-id}/team.yaml."""

    team_id: str
    name: str = ""
    description: str = ""
    created: str = ""
    schema_version: int = 1
    members: list[TeamMember] = Field(default_factory=list)
    knowledge_repo: KnowledgeRepo = Field(default_factory=KnowledgeRepo)
    policies: TeamPolicy = Field(default_factory=TeamPolicy)
    defaults: dict[str, Any] = Field(default_factory=dict)

    # ── Serialization ──────────────────────────────────────────

    def to_yaml(self) -> str:
        return yaml.dump(
            self.model_dump(exclude_none=True),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    @classmethod
    def from_yaml(cls, text: str) -> TeamConfig:
        data = yaml.safe_load(text)
        return cls.model_validate(data)

    # ── File I/O ───────────────────────────────────────────────

    def write(self) -> Path:
        """Write config to ~/.agent-flow/teams/{team_id}/team.yaml."""
        team_dir = TEAMS_DIR / self.team_id
        team_dir.mkdir(parents=True, exist_ok=True)
        path = team_dir / TEAM_CONFIG_FILENAME
        path.write_text(self.to_yaml(), encoding="utf-8")
        return path

    @classmethod
    def read(cls, team_id: str) -> TeamConfig | None:
        """Read config from disk, returns None if not found."""
        path = TEAMS_DIR / team_id / TEAM_CONFIG_FILENAME
        if not path.exists():
            return None
        return cls.from_yaml(path.read_text(encoding="utf-8"))

    @classmethod
    def remove(cls, team_id: str) -> bool:
        """Remove team config file. Returns True if deleted."""
        path = TEAMS_DIR / team_id / TEAM_CONFIG_FILENAME
        if path.exists():
            path.unlink()
            return True
        return False

    # ── Membership ─────────────────────────────────────────────

    def get_member(self, user_id: str) -> TeamMember | None:
        for m in self.members:
            if m.user_id == user_id:
                return m
        return None

    def add_member(self, user_id: str, display_name: str = "", role: str = ROLE_MEMBER) -> None:
        if self.get_member(user_id) is not None:
            return
        self.members.append(
            TeamMember(
                user_id=user_id,
                display_name=display_name,
                role=role,
                joined=datetime.now().strftime("%Y-%m-%d"),
            )
        )

    def remove_member(self, user_id: str) -> bool:
        before = len(self.members)
        self.members = [m for m in self.members if m.user_id != user_id]
        return len(self.members) < before

    # ── Permission checks ──────────────────────────────────────

    def has_role(self, user_id: str, min_role: str) -> bool:
        """Check if a user has at least the given role level."""
        member = self.get_member(user_id)
        if member is None:
            return False
        return ROLE_HIERARCHY.get(member.role, -1) >= ROLE_HIERARCHY.get(min_role, 0)

    def can_promote_skill(self, user_id: str) -> bool:
        return self.has_role(user_id, self.policies.skill_approval)

    def can_edit_wiki(self, user_id: str) -> bool:
        return self.has_role(user_id, self.policies.wiki_edit)

    def can_install_hooks(self, user_id: str) -> bool:
        return self.has_role(user_id, self.policies.hook_install)

    def can_promote_knowledge(self, user_id: str) -> bool:
        return self.has_role(user_id, self.policies.knowledge_promotion)

    # ── Directory helpers ──────────────────────────────────────

    def knowledge_dir(self) -> Path:
        return TEAMS_DIR / self.team_id / "knowledge"

    def skills_dir(self) -> Path:
        return self.knowledge_dir() / "skills"

    def wiki_dir(self) -> Path:
        return self.knowledge_dir() / "wiki"

    def hooks_dir(self) -> Path:
        return self.knowledge_dir() / "hooks"

    def state_dir(self) -> Path:
        return TEAMS_DIR / self.team_id / "state"

    def ensure_dirs(self) -> None:
        """Create team directory structure if it doesn't exist."""
        for d in [
            self.knowledge_dir(),
            self.skills_dir(),
            self.wiki_dir(),
            self.hooks_dir(),
            self.knowledge_dir() / "policies",
            self.state_dir(),
            self.state_dir() / "handoffs",
            TEAMS_DIR / self.team_id / "members",
        ]:
            d.mkdir(parents=True, exist_ok=True)


# ── Project-team binding helpers ───────────────────────────────


def get_project_team_id(project_dir: Path) -> str | None:
    """Read the team_id from project's .agent-flow/config.yaml.

    Returns None if the project has no team binding.
    """
    config_path = project_dir / ".agent-flow" / "config.yaml"
    if not config_path.is_file():
        return None
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        team = data.get("team")
        if isinstance(team, dict):
            return team.get("team_id") or None
        return None
    except Exception:
        return None


def get_project_team_binding(project_dir: Path) -> ProjectTeamBinding | None:
    """Read the full team binding from project's .agent-flow/config.yaml."""
    config_path = project_dir / ".agent-flow" / "config.yaml"
    if not config_path.is_file():
        return None
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        team = data.get("team")
        if isinstance(team, dict) and team.get("team_id"):
            return ProjectTeamBinding.model_validate(team)
        return None
    except Exception:
        return None


def set_project_team_binding(project_dir: Path, binding: ProjectTeamBinding) -> None:
    """Write or update the team section in project's .agent-flow/config.yaml."""
    config_path = project_dir / ".agent-flow" / "config.yaml"
    data: dict[str, Any] = {}
    if config_path.is_file():
        try:
            existing = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                data = existing
        except Exception:
            pass
    data["team"] = binding.model_dump(exclude_none=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def team_skills_dir(project_dir: Path) -> Path | None:
    """Resolve team skills directory from project's team binding."""
    team_id = get_project_team_id(project_dir)
    if not team_id:
        return None
    path = TEAMS_DIR / team_id / "knowledge" / "skills"
    return path if path.is_dir() else None


def team_wiki_dir(project_dir: Path) -> Path | None:
    """Resolve team wiki directory from project's team binding."""
    team_id = get_project_team_id(project_dir)
    if not team_id:
        return None
    path = TEAMS_DIR / team_id / "knowledge" / "wiki"
    return path if path.is_dir() else None


def list_teams() -> list[TeamConfig]:
    """List all teams the current user is a member of."""
    teams: list[TeamConfig] = []
    if not TEAMS_DIR.is_dir():
        return teams
    for entry in sorted(TEAMS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        config = TeamConfig.read(entry.name)
        if config is not None:
            teams.append(config)
    return teams
