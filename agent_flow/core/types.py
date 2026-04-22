from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AssetKind = Literal["skill", "wiki", "reference", "tool", "hook", "soul"]
ResourceLayer = Literal["global", "team", "project"]


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
