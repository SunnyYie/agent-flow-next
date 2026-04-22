from pathlib import Path

from agent_flow.migrations.legacy import migrate_legacy_assets


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_migrate_legacy_assets(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    global_src = tmp_path / "global_src"
    project = tmp_path / "project"
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "agent_flow" / "resources"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "team_root"))

    write(legacy / ".agent-flow" / "skills" / "a" / "handler.md", "skill")
    write(legacy / ".dev-workflow" / "wiki" / "INDEX.md", "wiki")
    write(global_src / "hooks" / "runtime" / "context-guard.py", "print('generic')")
    write(global_src / "hooks" / "runtime" / "preflight-guard.py", "print('x')")
    write(global_src / "hooks" / "runtime" / "claude-md-bootstrap.py", "print('no')")
    write(global_src / "hooks" / "runtime" / "observation-recorder.py", "print('obs')")
    write(global_src / "hooks" / "runtime" / "session-starter.py", "print('start')")
    write(global_src / "hooks" / "runtime" / "session-end-recorder.py", "print('end')")
    write(global_src / "hooks" / "runtime" / "startup-context.py", "print('ctx')")
    write(global_src / "skills" / "integration" / "jira-workflow" / "SKILL.md", "jira")
    write(global_src / "skills" / "workflow" / "phase-review" / "SKILL.md", "phase")
    write(global_src / "skills" / "workflow" / "phase-review" / "handler.md", "handler")
    write(global_src / "wiki" / "patterns" / "feishu" / "a.md", "feishu")
    write(global_src / "wiki" / "patterns" / "workflow" / "search-before-execute.md", "workflow")
    write(global_src / "skills" / "g" / "SKILL.md", "global-skill")
    write(project / ".agent-flow" / "teams" / "legacy-team" / "team.yaml", "team_id: legacy-team")

    report = migrate_legacy_assets(
        legacy_project_dir=legacy,
        global_source_dir=global_src,
        project_dir=project,
        team_id="acme",
    )

    assert not (project / ".agent-flow" / "skills").exists()
    assert not (project / ".agent-flow" / "wiki").exists()
    assert (project / ".agent-flow" / "souls" / "main.md").read_text(encoding="utf-8") == ""
    assert not (tmp_path / "agent_flow" / "resources" / "global" / "hooks").exists()
    assert (project / "agent_flow" / "templates" / "hooks" / "runtime" / "context-guard.py").is_file()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "claude-md-bootstrap.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "thinking-chain-enforce.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "search-tracker.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "phase-reminder.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "project-structure-enforce.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "preflight-enforce.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "preflight-guard.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "observation-recorder.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "session-starter.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "session-end-recorder.py").exists()
    assert not (project / "agent_flow" / "templates" / "hooks" / "runtime" / "startup-context.py").exists()
    assert (project / "agent_flow" / "templates" / "hooks" / "README.md").is_file()
    assert not (tmp_path / "agent_flow" / "resources" / "global" / "skills" / "integration").exists()
    assert not (tmp_path / "agent_flow" / "resources" / "global" / "skills" / "workflow" / "phase-review" / "handler.md").exists()
    assert not (tmp_path / "agent_flow" / "resources" / "global" / "wiki" / "patterns" / "feishu" / "a.md").exists()
    assert (tmp_path / "agent_flow" / "resources" / "global" / "skills" / "workflow" / "phase-review" / "SKILL.md").is_file()
    assert (tmp_path / "agent_flow" / "resources" / "global" / "wiki" / "patterns" / "workflow" / "search-before-execute.md").is_file()
    assert (tmp_path / "agent_flow" / "resources" / "global" / "skills" / "g" / "SKILL.md").is_file()
    assert (tmp_path / "team_root" / "acme").is_dir()
    assert not (project / ".agent-flow" / "teams").exists()
    assert not (tmp_path / "agent_flow" / "resources" / "teams").exists()
    assert report["copied"] >= 1
    assert report["template_hooks_root"].endswith("agent_flow/templates/hooks")
    assert report["include_project_knowledge"] is False


def test_migrate_legacy_assets_with_project_knowledge(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    global_src = tmp_path / "global_src"
    project = tmp_path / "project"
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "agent_flow" / "resources"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "team_root"))

    write(legacy / ".agent-flow" / "skills" / "a" / "handler.md", "skill")
    write(legacy / ".dev-workflow" / "wiki" / "INDEX.md", "wiki")
    write(global_src / "skills" / "g" / "SKILL.md", "global-skill")

    report = migrate_legacy_assets(
        legacy_project_dir=legacy,
        global_source_dir=global_src,
        project_dir=project,
        team_id="acme",
        include_project_knowledge=True,
    )

    assert (project / ".agent-flow" / "skills" / "a" / "SKILL.md").is_file()
    assert (project / ".agent-flow" / "wiki" / "INDEX.md").is_file()
    assert report["include_project_knowledge"] is True


def test_migrate_skips_same_global_source(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy"
    global_root = tmp_path / "agent_flow" / "resources" / "global"
    project = tmp_path / "project"
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "agent_flow" / "resources"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "team_root"))

    write(legacy / ".agent-flow" / "skills" / "a" / "SKILL.md", "skill")
    write(global_root / "skills" / "g" / "SKILL.md", "global-skill")

    report = migrate_legacy_assets(
        legacy_project_dir=legacy,
        global_source_dir=global_root,
        project_dir=project,
        team_id="acme",
    )

    assert not (project / ".agent-flow" / "skills").exists()
    assert (global_root / "skills" / "g" / "SKILL.md").is_file()
    assert report["copied"] >= 0
