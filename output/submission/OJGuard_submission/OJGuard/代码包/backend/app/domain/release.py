from pydantic import BaseModel, Field

from backend.app.domain.models import ReleaseDecision


class ReleasePolicy(BaseModel):
    version: str = "0.1.0"
    block_confirmed_severities: set[str] = Field(default_factory=lambda: {"critical", "high"})
    warning_confirmed_severities: set[str] = Field(default_factory=lambda: {"medium", "low"})
    require_replay_for_blocking: bool = True
    require_second_approval: bool = True


class ReleaseGateResult(BaseModel):
    policy_version: str
    decision: ReleaseDecision
    blocking_finding_ids: list[str] = Field(default_factory=list)
    warning_finding_ids: list[str] = Field(default_factory=list)
    review_finding_ids: list[str] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)
