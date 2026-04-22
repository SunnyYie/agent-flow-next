from pathlib import Path

from agent_flow.core.config import init_global, init_project, init_team, layer_root, templates_hooks_root


def test_init_creates_expected_layer_directories(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "repo_resources"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "team_root"))

    global_root = init_global(project_dir=tmp_path)
    team_root = init_team("acme", project_dir=tmp_path)
    project_root = init_project(tmp_path / "project")

    assert global_root == layer_root("global", project_dir=tmp_path)
    assert team_root == layer_root("team", team_id="acme", project_dir=tmp_path)
    assert team_root == tmp_path / "team_root" / "acme"
    assert project_root == layer_root("project", project_dir=tmp_path / "project")

    for root in [global_root, team_root]:
        assert (root / "skills").is_dir()
        assert (root / "wiki").is_dir()
        assert (root / "references").is_dir()
        assert (root / "tools").is_dir()
        assert (root / "souls").is_dir()
    assert not (global_root / "hooks").exists()
    assert (templates_hooks_root(project_dir=tmp_path) / "runtime").is_dir()
    assert (templates_hooks_root(project_dir=tmp_path) / "governance").is_dir()
    assert (team_root / "hooks" / "runtime").is_dir()
    assert (team_root / "hooks" / "governance").is_dir()

    assert (project_root / "hooks" / "runtime").is_dir()
    assert (project_root / "hooks" / "governance").is_dir()
    assert (project_root / "state").is_dir()
    assert (project_root / "souls").is_dir()
    assert (project_root / "souls" / "main.md").read_text(encoding="utf-8") == ""
    assert not (project_root / "skills").exists()
    assert not (project_root / "wiki").exists()
