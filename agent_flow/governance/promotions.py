from __future__ import annotations

from datetime import datetime, timezone
import shutil
import uuid
from pathlib import Path

import yaml

from agent_flow.core.types import is_promotable_kind_v1, is_valid_promotion_path_v1

class PromotionManager:
    def __init__(self, project_root: Path, team_root: Path, global_root: Path) -> None:
        self.project_root = Path(project_root)
        self.team_root = Path(team_root)
        self.global_root = Path(global_root)
        self.promotions_dir = self.team_root / "promotions"
        self.audit_dir = self.team_root / "audit" / "promotions"

    def _proposal_dir(self, proposal_id: str) -> Path:
        return self.promotions_dir / proposal_id

    def _asset_target_path(self, kind: str, name: str, layer: str) -> Path:
        if layer == "project":
            root = self.project_root
        elif layer == "team":
            root = self.team_root
        elif layer == "global":
            root = self.global_root
        else:
            raise ValueError(f"unknown layer: {layer}")

        if kind == "skill":
            return root / "skills" / name / "SKILL.md"
        if kind == "wiki":
            return root / "wiki" / f"{name}.md"
        if kind == "hook":
            return root / "hooks" / f"{name}.py"
        raise ValueError(f"unsupported promotion kind: {kind}")

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def submit(self, kind: str, name: str, from_layer: str, to_layer: str, team_id: str, source_path: str) -> str:
        if not is_promotable_kind_v1(kind):
            raise ValueError(f"unsupported promotion kind: {kind}")
        if not is_valid_promotion_path_v1(kind, from_layer, to_layer):
            raise ValueError(f"invalid promotion path: {from_layer}->{to_layer}")

        source = Path(source_path)
        if not source.exists() or not source.is_file():
            raise ValueError(f"source path does not exist: {source_path}")

        target_path = self._asset_target_path(kind=kind, name=name, layer=to_layer)
        proposal_id = f"p-{uuid.uuid4().hex[:8]}"
        pdir = self._proposal_dir(proposal_id)
        (pdir / "snapshot").mkdir(parents=True, exist_ok=True)
        (pdir / "human-reviews").mkdir(parents=True, exist_ok=True)
        (pdir / "ai-reviews").mkdir(parents=True, exist_ok=True)
        snapshot_path = pdir / "snapshot" / source.name
        shutil.copy2(source, snapshot_path)
        proposal = {
            "proposal_id": proposal_id,
            "kind": kind,
            "name": name,
            "from_layer": from_layer,
            "to_layer": to_layer,
            "team_id": team_id,
            "source_path": source_path,
            "target_path": str(target_path),
            "conflict_reason": "",
            "status": "pending",
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
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
        if team_id and team_id != self.team_root.name:
            raise ValueError(f"team_id mismatch: expected {self.team_root.name}, got {team_id}")
        if (self.team_root / ".dirty").exists():
            raise ValueError("team repo is dirty")
        if (self.team_root / ".behind").exists():
            raise ValueError("team repo is behind remote")

    def _write_audit(self, proposal_id: str, proposal: dict, decision: dict, humans: list[dict], ais: list[dict]) -> None:
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        audit_path = self.audit_dir / f"{datetime.now().date().isoformat()}.yaml"
        existing = []
        if audit_path.exists():
            existing = yaml.safe_load(audit_path.read_text(encoding="utf-8")) or []
        existing.append(
            {
                "timestamp": self._now_iso(),
                "proposal_id": proposal_id,
                "kind": proposal["kind"],
                "name": proposal["name"],
                "from_layer": proposal["from_layer"],
                "to_layer": proposal["to_layer"],
                "team_id": proposal["team_id"],
                "decision": decision["decision"],
                "target_path": proposal.get("target_path", ""),
                "human_reviewers": [h.get("reviewer", "") for h in humans if h.get("decision") == "approved"],
                "ai_profiles": [a.get("profile", "") for a in ais if a.get("decision") == "approved"],
            }
        )
        audit_path.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")

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

        source_path = Path(proposal["source_path"])
        target_path = Path(proposal.get("target_path", ""))
        if target_path.exists():
            proposal["conflict_reason"] = f"target already exists: {target_path}"
            proposal["updated_at"] = self._now_iso()
            (self._proposal_dir(proposal_id) / "proposal.yaml").write_text(
                yaml.safe_dump(proposal, sort_keys=False),
                encoding="utf-8",
            )
            raise ValueError(f"target already exists: {target_path}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

        decision = {
            "proposal_id": proposal_id,
            "decision": "approved",
            "reason": "all required reviews passed",
        }
        path = self._proposal_dir(proposal_id) / "decision.yaml"
        path.write_text(yaml.safe_dump(decision, sort_keys=False), encoding="utf-8")

        proposal["status"] = "executed"
        proposal["updated_at"] = self._now_iso()
        (self._proposal_dir(proposal_id) / "proposal.yaml").write_text(
            yaml.safe_dump(proposal, sort_keys=False),
            encoding="utf-8",
        )
        self._write_audit(proposal_id=proposal_id, proposal=proposal, decision=decision, humans=humans, ais=ais)
        return decision

    def status(self, proposal_id: str) -> dict:
        pdir = self._proposal_dir(proposal_id)
        proposal = yaml.safe_load((pdir / "proposal.yaml").read_text(encoding="utf-8"))
        has_decision = (pdir / "decision.yaml").exists()
        return {
            "proposal": proposal,
            "has_decision": has_decision,
        }
