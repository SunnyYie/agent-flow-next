from pathlib import Path

from agent_flow.resources.resolver import ResourceResolver


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_precedence_and_reference_aggregation(tmp_path):
    g = tmp_path / "g"
    t = tmp_path / "t"
    p = tmp_path / "p"

    write(g / "skills" / "lint" / "SKILL.md", "global")
    write(t / "skills" / "lint" / "SKILL.md", "team")
    write(p / "skills" / "lint" / "SKILL.md", "project")

    write(g / "references" / "a.md", "ga")
    write(t / "references" / "b.md", "tb")
    write(p / "references" / "c.md", "pc")

    resolver = ResourceResolver(global_root=g, team_root=t, project_root=p)
    resolved = resolver.resolve_all()

    assert resolved["skills"]["lint"].layer == "project"
    assert set(resolved["references"].keys()) == {"a", "b", "c"}


def test_skill_handler_md_is_supported_for_legacy_content(tmp_path):
    g = tmp_path / "g"
    write(g / "skills" / "legacy-skill" / "handler.md", "legacy")

    resolver = ResourceResolver(global_root=g)
    resolved = resolver.resolve_all()

    assert "legacy-skill" in resolved["skills"]
    assert resolved["skills"]["legacy-skill"].layer == "global"


def test_governance_hook_not_overridden_by_project(tmp_path):
    g = tmp_path / "g"
    t = tmp_path / "t"
    p = tmp_path / "p"

    write(t / "hooks" / "governance" / "approve.py", "team")
    write(p / "hooks" / "governance" / "approve.py", "project")

    resolver = ResourceResolver(global_root=g, team_root=t, project_root=p)
    resolved = resolver.resolve_all()

    assert resolved["hooks"]["governance/approve.py"].layer == "team"


def test_soul_fallback_by_role(tmp_path):
    g = tmp_path / "g"
    t = tmp_path / "t"
    p = tmp_path / "p"

    write(g / "souls" / "reviewer.md", "global")
    write(t / "souls" / "coder.md", "team")
    write(p / "souls" / "planner.md", "project")

    resolver = ResourceResolver(global_root=g, team_root=t, project_root=p)

    assert resolver.resolve_soul("planner").layer == "project"
    assert resolver.resolve_soul("coder").layer == "team"
    assert resolver.resolve_soul("reviewer").layer == "global"
