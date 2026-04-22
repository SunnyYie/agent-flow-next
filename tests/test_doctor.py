from pathlib import Path

from click.testing import CliRunner

from agent_flow.cli.main import cli
from agent_flow.core.doctor import run_doctor


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_doctor_reports_key_issues(tmp_path):
    project = tmp_path / "project"
    root = project / ".agent-flow"
    write(root / "skills" / "x" / "SKILL.md", "x")
    write(root / "hooks" / "governance" / "approve.py", "x")

    report = run_doctor(project_dir=project, global_root=tmp_path / "global", team_root=tmp_path / "team")

    assert any("missing soul" in issue.lower() for issue in report["issues"])


def test_doctor_json_output(tmp_path, monkeypatch):
    project = tmp_path / "project"
    root = project / ".agent-flow"
    write(root / "souls" / "main.md", "main")
    write(root / "config.yaml", "name: p")
    monkeypatch.chdir(project)
    monkeypatch.setenv("AGENT_FLOW_RESOURCES_ROOT", str(tmp_path / "global-res"))
    monkeypatch.setenv("AGENT_FLOW_TEAM_ROOT", str(tmp_path / "team-res"))

    runner = CliRunner()
    result = runner.invoke(cli, ["doctor", "--json"])

    assert result.exit_code == 0
    assert '"ok"' in result.output
    assert '"counts"' in result.output
