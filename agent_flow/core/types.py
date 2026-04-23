from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

AssetKind = Literal["skill", "wiki", "reference", "tool", "hook", "soul"]
ResourceLayer = Literal["global", "team", "project"]

PROMOTABLE_KINDS_V1: set[str] = {"skill", "wiki", "hook"}

VALID_PROMOTION_PATHS_V1: dict[str, set[tuple[str, str]]] = {
    "skill": {("project", "team"), ("team", "global")},
    "wiki": {("project", "team"), ("team", "global")},
    "hook": {("project", "team"), ("team", "global")},
}


def is_promotable_kind_v1(kind: str) -> bool:
    return kind in PROMOTABLE_KINDS_V1


def is_valid_promotion_path_v1(kind: str, from_layer: str, to_layer: str) -> bool:
    return (from_layer, to_layer) in VALID_PROMOTION_PATHS_V1.get(kind, set())


class AssetMetadata(BaseModel):
    name: str
    kind: AssetKind
    layer: ResourceLayer
    owner: str = ""
    version: str = ""
    status: str = "active"
    review_state: str = ""
    source_path: str


class ResolvedAsset(BaseModel):
    metadata: AssetMetadata
    path: str


class GlobalConfig(BaseModel):
    schema_version: int = 1


class TeamConfig(BaseModel):
    team_id: str
    name: str = ""
    schema_version: int = 1


class ProjectConfig(BaseModel):
    name: str
    team_id: str = ""
    schema_version: int = 1


class PromotionProposal(BaseModel):
    proposal_id: str
    kind: str
    name: str
    from_layer: ResourceLayer
    to_layer: ResourceLayer
    team_id: str
    source_path: str
    status: str = "pending"
    target_path: str = ""
    conflict_reason: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HumanReviewRecord(BaseModel):
    reviewer: str
    role: str
    decision: str
    summary: str = ""


class AIReviewRecord(BaseModel):
    profile: str
    decision: str
    summary: str
    risks: list[str] = Field(default_factory=list)
    reusability: str = ""
    reasoning_digest: str = ""


class PromotionDecision(BaseModel):
    proposal_id: str
    decision: str
    reason: str
