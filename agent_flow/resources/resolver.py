from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ResolvedEntry:
    key: str
    layer: str
    path: Path
    shadowed_by: str = ""


@dataclass
class ResolveResult:
    skills: dict[str, ResolvedEntry] = field(default_factory=dict)
    wiki: dict[str, ResolvedEntry] = field(default_factory=dict)
    references: dict[str, ResolvedEntry] = field(default_factory=dict)
    tools: dict[str, ResolvedEntry] = field(default_factory=dict)
    hooks: dict[str, ResolvedEntry] = field(default_factory=dict)
    souls: dict[str, ResolvedEntry] = field(default_factory=dict)


class ResourceResolver:
    def __init__(self, global_root: Path, team_root: Path | None = None, project_root: Path | None = None) -> None:
        self.global_root = Path(global_root)
        self.team_root = Path(team_root) if team_root else None
        self.project_root = Path(project_root) if project_root else None

    def _collect(self, root: Path, rel: str, suffix: str = ".md") -> dict[str, Path]:
        target = root / rel
        if not target.exists():
            return {}
        items: dict[str, Path] = {}
        for p in target.rglob("*"):
            if p.is_dir():
                continue
            if suffix and p.suffix.lower() != suffix:
                continue
            if rel == "skills":
                if p.name not in {"SKILL.md", "handler.md"}:
                    continue
                key = p.parent.name
            else:
                rel_path = p.relative_to(target)
                if rel == "hooks":
                    key = str(rel_path)
                else:
                    key = str(rel_path.with_suffix(""))
            items[key] = p
        return items

    def _resolve_overlay(self, rel: str, suffix: str = ".md", governance_guard: bool = False) -> dict[str, ResolvedEntry]:
        result: dict[str, ResolvedEntry] = {}
        layers: list[tuple[str, Path | None]] = [
            ("global", self.global_root),
            ("team", self.team_root),
            ("project", self.project_root),
        ]
        for layer, root in layers:
            if root is None:
                continue
            current = self._collect(root, rel, suffix=suffix)
            for key, path in current.items():
                if governance_guard and layer == "project" and key.startswith("governance/") and key in result:
                    continue
                result[key] = ResolvedEntry(key=key, layer=layer, path=path)
        return result

    def resolve_all(self) -> dict[str, dict[str, ResolvedEntry]]:
        references: dict[str, ResolvedEntry] = {}
        for layer, root in [("global", self.global_root), ("team", self.team_root), ("project", self.project_root)]:
            if root is None:
                continue
            for key, path in self._collect(root, "references", suffix=".md").items():
                references[key] = ResolvedEntry(key=key, layer=layer, path=path)

        return {
            "skills": self._resolve_overlay("skills", suffix=".md"),
            "wiki": self._resolve_overlay("wiki", suffix=".md"),
            "references": references,
            "tools": self._resolve_overlay("tools", suffix=".yaml"),
            "hooks": self._resolve_overlay("hooks", suffix=".py", governance_guard=True),
            "souls": self._resolve_overlay("souls", suffix=".md"),
        }

    def resolve_soul(self, role: str) -> ResolvedEntry | None:
        all_souls = self.resolve_all()["souls"]
        return all_souls.get(role)
