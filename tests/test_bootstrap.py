from click.testing import CliRunner

from agent_flow.cli.main import cli
from agent_flow.core.config import init_global, init_project, init_team, init_team_flow, layer_root, templates_hooks_root


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


def test_init_team_flow_generates_summary_indexes(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "repo_resources"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "team_root"))

    global_root = init_global(project_dir=tmp_path)
    # skills scenes
    (global_root / "skills" / "workflow" / "a" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "skills" / "workflow" / "a" / "SKILL.md").write_text("a", encoding="utf-8")
    (global_root / "skills" / "workflow" / "b" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "skills" / "workflow" / "b" / "SKILL.md").write_text("b", encoding="utf-8")
    (global_root / "skills" / "workflow" / "c" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "skills" / "workflow" / "c" / "SKILL.md").write_text("c", encoding="utf-8")
    (global_root / "skills" / "workflow" / "d" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "skills" / "workflow" / "d" / "SKILL.md").write_text("d", encoding="utf-8")
    (global_root / "skills" / "research" / "web-research" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "skills" / "research" / "web-research" / "SKILL.md").write_text("r", encoding="utf-8")

    # wiki scenes
    (global_root / "wiki" / "concepts" / "agent-roles.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "wiki" / "concepts" / "agent-roles.md").write_text("roles", encoding="utf-8")
    (global_root / "wiki" / "concepts" / "memory-systems.md").write_text("memory", encoding="utf-8")
    (global_root / "wiki" / "patterns" / "workflow" / "search-before-execute.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "wiki" / "patterns" / "workflow" / "search-before-execute.md").write_text("pattern", encoding="utf-8")

    team_root = init_team_flow("acme", project_dir=tmp_path)

    skills_index = (team_root / "skills" / "Index.md").read_text(encoding="utf-8")
    wiki_index = (team_root / "wiki" / "Index.md").read_text(encoding="utf-8")

    assert "# Team Skills Index" in skills_index
    assert "[workflow]" in skills_index
    assert "[research]" in skills_index
    assert "workflow/d/SKILL.md" not in skills_index

    assert "# Team Wiki Index" in wiki_index
    assert "[concepts]" in wiki_index
    assert "[patterns]" in wiki_index
    assert "search-before-execute.md" in wiki_index


def test_init_team_flow_command_creates_team_indexes(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "resources"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "teams"))

    global_root = tmp_path / "resources" / "global"
    (global_root / "skills" / "workflow" / "phase-review" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "skills" / "workflow" / "phase-review" / "SKILL.md").write_text("phase", encoding="utf-8")
    (global_root / "wiki" / "concepts" / "agent-roles.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "wiki" / "concepts" / "agent-roles.md").write_text("roles", encoding="utf-8")

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["init-team-flow", "--team-id", "acme"])

    assert result.exit_code == 0
    team_root = tmp_path / "teams" / "acme"
    assert (team_root / "skills" / "Index.md").is_file()
    assert (team_root / "wiki" / "Index.md").is_file()


def test_asset_list_show_create_and_lint_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "resources"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "teams"))
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)

    global_root = init_global(project_dir=project)
    init_project(project)
    (global_root / "skills" / "workflow" / "phase-review" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (global_root / "skills" / "workflow" / "phase-review" / "SKILL.md").write_text("phase", encoding="utf-8")

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        monkeypatch.chdir(project)

        created = runner.invoke(
            cli,
            ["asset", "create", "--kind", "wiki", "--name", "concepts/new-doc", "--layer", "project"],
        )
        assert created.exit_code == 0

        listed = runner.invoke(cli, ["asset", "list", "--kind", "wiki"])
        assert listed.exit_code == 0
        assert "concepts/new-doc" in listed.output

        shown = runner.invoke(cli, ["asset", "show", "--kind", "wiki", "--name", "concepts/new-doc"])
        assert shown.exit_code == 0
        assert "layer: project" in shown.output

        linted = runner.invoke(cli, ["asset", "lint", "--json"])
        assert linted.exit_code == 0
        assert '"ok"' in linted.output


def test_team_list_and_info_commands(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "resources"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "teams"))
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    init_global(project_dir=project)
    init_project(project)
    init_team_flow("acme", name="Acme Team", project_dir=project)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        monkeypatch.chdir(project)

        list_result = runner.invoke(cli, ["team", "list"])
        assert list_result.exit_code == 0
        assert "acme" in list_result.output
        assert "Acme Team" in list_result.output

        info_result = runner.invoke(cli, ["team", "info", "--team-id", "acme"])
        assert info_result.exit_code == 0
        assert "team_id: acme" in info_result.output
        assert "asset_counts:" in info_result.output
