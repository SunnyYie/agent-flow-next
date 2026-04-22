from pathlib import Path

import pytest

from agent_flow.governance.promotions import PromotionManager


def test_project_to_team_finalize_requires_human_and_ai(tmp_path):
    mgr = PromotionManager(base_dir=tmp_path)
    pid = mgr.submit(
        kind="skill",
        name="lint",
        from_layer="project",
        to_layer="team",
        team_id="acme",
        source_path="skills/lint/SKILL.md",
    )

    with pytest.raises(ValueError, match="human review"):
        mgr.finalize(pid)

    mgr.add_human_review(pid, reviewer="lead-a", role="lead", decision="approved")
    with pytest.raises(ValueError, match="AI review"):
        mgr.finalize(pid)

    mgr.add_ai_review(pid, profile="safe", decision="approved", summary="ok")
    decision = mgr.finalize(pid)
    assert decision["decision"] == "approved"


def test_team_to_global_requires_two_humans_and_distinct_ai_profiles(tmp_path):
    mgr = PromotionManager(base_dir=tmp_path)
    pid = mgr.submit(
        kind="skill",
        name="lint",
        from_layer="team",
        to_layer="global",
        team_id="acme",
        source_path="skills/lint/SKILL.md",
    )

    mgr.add_human_review(pid, reviewer="lead-a", role="lead", decision="approved")
    mgr.add_human_review(pid, reviewer="lead-b", role="lead", decision="approved")

    mgr.add_ai_review(pid, profile="safe", decision="approved", summary="ok")
    with pytest.raises(ValueError, match="2 distinct AI profiles"):
        mgr.finalize(pid)

    mgr.add_ai_review(pid, profile="reuse", decision="approved", summary="ok")
    decision = mgr.finalize(pid)
    assert decision["decision"] == "approved"


def test_finalize_blocks_dirty_repo(tmp_path):
    team_root = tmp_path / "teams" / "acme"
    team_root.mkdir(parents=True)
    (team_root / ".dirty").write_text("1", encoding="utf-8")

    mgr = PromotionManager(base_dir=tmp_path)
    pid = mgr.submit(
        kind="skill",
        name="lint",
        from_layer="project",
        to_layer="team",
        team_id="acme",
        source_path="skills/lint/SKILL.md",
    )
    mgr.add_human_review(pid, reviewer="lead-a", role="lead", decision="approved")
    mgr.add_ai_review(pid, profile="safe", decision="approved", summary="ok")

    with pytest.raises(ValueError, match="dirty"):
        mgr.finalize(pid)
