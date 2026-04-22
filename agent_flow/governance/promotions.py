from __future__ import annotations

import uuid
from pathlib import Path

import yaml


class PromotionManager:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        self.promotions_dir = self.base_dir / "promotions"
        self.teams_dir = self.base_dir / "teams"

    def _proposal_dir(self, proposal_id: str) -> Path:
        return self.promotions_dir / proposal_id

    def submit(self, kind: str, name: str, from_layer: str, to_layer: str, team_id: str, source_path: str) -> str:
        proposal_id = f"p-{uuid.uuid4().hex[:8]}"
        pdir = self._proposal_dir(proposal_id)
        (pdir / "snapshot").mkdir(parents=True, exist_ok=True)
        (pdir / "human-reviews").mkdir(parents=True, exist_ok=True)
        (pdir / "ai-reviews").mkdir(parents=True, exist_ok=True)
        proposal = {
            "proposal_id": proposal_id,
            "kind": kind,
            "name": name,
            "from_layer": from_layer,
            "to_layer": to_layer,
            "team_id": team_id,
            "source_path": source_path,
            "status": "pending",
        }
        (pdir / "proposal.yaml").write_text(yaml.safe_dump(proposal, sort_keys=False), encoding="utf-8")
        return proposal_id

    def add_human_review(self, proposal_id: str, reviewer: str, role: str, decision: str, summary: str = "") -> Path:
        pdir = self._proposal_dir(proposal_id) / "human-reviews"
        pdir.mkdir(parents=True, exist_ok=True)
        payload = {"reviewer": reviewer, "role": role, "decision": decision, "summary": summary}
        path = pdir / f"{reviewer}.yaml"
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return path

    def add_ai_review(self, proposal_id: str, profile: str, decision: str, summary: str, risks=None, reusability: str = "", reasoning_digest: str = "") -> Path:
        pdir = self._proposal_dir(proposal_id) / "ai-reviews"
        pdir.mkdir(parents=True, exist_ok=True)
        payload = {
            "profile": profile,
            "decision": decision,
            "summary": summary,
            "risks": risks or [],
            "reusability": reusability,
            "reasoning_digest": reasoning_digest,
        }
        path = pdir / f"{profile}.yaml"
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        return path

    def _load_reviews(self, proposal_id: str) -> tuple[list[dict], list[dict], dict]:
        pdir = self._proposal_dir(proposal_id)
        proposal = yaml.safe_load((pdir / "proposal.yaml").read_text(encoding="utf-8"))
        human_reviews = []
        ai_reviews = []
        for f in (pdir / "human-reviews").glob("*.yaml"):
            human_reviews.append(yaml.safe_load(f.read_text(encoding="utf-8")))
        for f in (pdir / "ai-reviews").glob("*.yaml"):
            ai_reviews.append(yaml.safe_load(f.read_text(encoding="utf-8")))
        return human_reviews, ai_reviews, proposal

    def _check_team_repo_health(self, team_id: str) -> None:
        team_root = self.teams_dir / team_id
        if (team_root / ".dirty").exists():
            raise ValueError("team repo is dirty")
        if (team_root / ".behind").exists():
            raise ValueError("team repo is behind remote")

    def finalize(self, proposal_id: str) -> dict:
        humans, ais, proposal = self._load_reviews(proposal_id)

        approvals = [h for h in humans if h.get("decision") == "approved" and h.get("role") in {"lead", "admin", "maintainer"}]
        ai_approvals = [a for a in ais if a.get("decision") == "approved"]

        if proposal["to_layer"] in {"team", "global"}:
            self._check_team_repo_health(proposal["team_id"])

        if proposal["from_layer"] == "project" and proposal["to_layer"] == "team":
            if len(approvals) < 1:
                raise ValueError("missing required human review")
            if len(ai_approvals) < 1:
                raise ValueError("missing required AI review")

        if proposal["from_layer"] == "team" and proposal["to_layer"] == "global":
            unique_humans = {h.get("reviewer") for h in approvals}
            if len(unique_humans) < 2:
                raise ValueError("team->global requires 2 human approvals")
            profiles = [a.get("profile") for a in ai_approvals]
            if len(set(profiles)) < 2:
                raise ValueError("team->global requires 2 distinct AI profiles")

        decision = {
            "proposal_id": proposal_id,
            "decision": "approved",
            "reason": "all required reviews passed",
        }
        path = self._proposal_dir(proposal_id) / "decision.yaml"
        path.write_text(yaml.safe_dump(decision, sort_keys=False), encoding="utf-8")

        proposal["status"] = "approved"
        (self._proposal_dir(proposal_id) / "proposal.yaml").write_text(
            yaml.safe_dump(proposal, sort_keys=False),
            encoding="utf-8",
        )
        return decision

    def status(self, proposal_id: str) -> dict:
        pdir = self._proposal_dir(proposal_id)
        proposal = yaml.safe_load((pdir / "proposal.yaml").read_text(encoding="utf-8"))
        has_decision = (pdir / "decision.yaml").exists()
        return {
            "proposal": proposal,
            "has_decision": has_decision,
        }
