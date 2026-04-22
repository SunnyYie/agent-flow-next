from __future__ import annotations

from pathlib import Path

from agent_flow.resources.resolver import ResourceResolver


def run_doctor(project_dir: Path, global_root: Path, team_root: Path | None = None) -> dict:
    project_root = Path(project_dir) / ".agent-flow"
    resolver = ResourceResolver(global_root=global_root, team_root=team_root, project_root=project_root)
    resolved = resolver.resolve_all()

    issues: list[str] = []

    if not resolved["souls"]:
        issues.append("Missing soul definitions across all layers")

    if project_root.exists() and not (project_root / "config.yaml").exists():
        issues.append("Missing project config.yaml")

    # Shadow warning on governance hooks in project when team/global already has the same key.
    pgov = (project_root / "hooks" / "governance") if project_root.exists() else None
    if pgov and pgov.exists():
        for p in pgov.rglob("*.py"):
            rel = f"governance/{p.relative_to(pgov)}"
            resolved_entry = resolved["hooks"].get(rel)
            if resolved_entry and resolved_entry.layer != "project":
                issues.append(f"Governance hook shadowed in project: {rel}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "counts": {k: len(v) for k, v in resolved.items()},
    }
