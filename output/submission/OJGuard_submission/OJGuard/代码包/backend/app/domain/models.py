from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class RunStage(StrEnum):
    RECEIVED = "RECEIVED"
    BASELINE_VALIDATING = "BASELINE_VALIDATING"
    ANALYZING = "ANALYZING"
    TESTING = "TESTING"
    EVIDENCE_REVIEW = "EVIDENCE_REVIEW"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    PASS_CANDIDATE = "PASS_CANDIDATE"
    PATCH_PENDING_APPROVAL = "PATCH_PENDING_APPROVAL"
    REVALIDATING = "REVALIDATING"
    READY_FOR_RELEASE = "READY_FOR_RELEASE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class ConfidenceClass(StrEnum):
    CONFIRMED = "CONFIRMED"
    STATICALLY_PROVEN = "STATICALLY_PROVEN"
    SUSPECTED = "SUSPECTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalState(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"


class ApprovalAction(StrEnum):
    APPLY_PATCH_TO_WORKING_COPY = "APPLY_PATCH_TO_WORKING_COPY"
    CONFIRM_RELEASE_CANDIDATE = "CONFIRM_RELEASE_CANDIDATE"
    ACCEPT_RISK = "ACCEPT_RISK"


class PatchStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    REGRESSION_PASSED = "REGRESSION_PASSED"
    REGRESSION_FAILED = "REGRESSION_FAILED"
    RELEASE_CONFIRMED = "RELEASE_CONFIRMED"


class PatchRisk(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ReleaseDecision(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class RunBudgets(BaseModel):
    test_cases: int = Field(default=200, ge=1, le=10_000)
    execution_seconds: int = Field(default=180, ge=1, le=3600)
    llm_calls: int = Field(default=20, ge=0, le=100)


class TaskContext(BaseModel):
    task_id: str = Field(min_length=1, max_length=100)
    package_id: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=100)
    stage: RunStage = RunStage.RECEIVED
    contract_artifact_id: str | None = None
    active_hypothesis_ids: list[str] = Field(default_factory=list)
    confirmed_finding_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    approval_state: ApprovalState = ApprovalState.NOT_REQUESTED
    budgets: RunBudgets = Field(default_factory=RunBudgets)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Finding(BaseModel):
    id: str
    package_id: str
    run_id: str
    source_agent: str
    category: str
    severity: Severity
    confidence_class: ConfidenceClass
    description: str
    hypothesis_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    replay_action: str | None = None
    requires_human_review: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class HypothesisStatus(StrEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class Hypothesis(BaseModel):
    id: str
    package_id: str
    run_id: str
    source_agent: str
    category: str
    description: str
    confidence: float = Field(ge=0, le=1)
    severity: Severity
    verification_plan: dict[str, Any]
    source_locations: list[str] = Field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.PENDING_VERIFICATION
    created_at: datetime = Field(default_factory=utc_now)


class Evidence(BaseModel):
    id: str
    package_id: str
    run_id: str
    type: str
    producer: str
    artifact_path: str
    sha256: str
    tool_version: str
    seed: int | None = None
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class AgentEvent(BaseModel):
    id: str
    task_id: str
    run_id: str
    agent: str
    event_type: str
    summary: str
    artifact_ids: list[str] = Field(default_factory=list)
    matrix_room_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ApprovalRecord(BaseModel):
    id: str
    run_id: str
    action: ApprovalAction
    state: ApprovalState
    actor: str
    target_id: str
    reason: str | None = None
    before_sha256: str | None = None
    after_sha256: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class PatchFileChange(BaseModel):
    relative_path: str
    before_sha256: str | None = None
    after_sha256: str
    unified_diff: str
    after_content: str


class PatchCandidate(BaseModel):
    id: str
    package_id: str
    run_id: str
    title: str
    rationale: str
    risk: PatchRisk
    finding_ids: list[str]
    regression_scope: list[str]
    changes: list[PatchFileChange]
    status: PatchStatus = PatchStatus.CANDIDATE
    working_copy_path: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
