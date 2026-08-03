from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .models import utc_now


class IncidentType(StrEnum):
    RUNTIME_REGRESSION = "runtime_regression"
    NODE_DEGRADATION = "node_degradation"
    CHECKER_DEFECT = "checker_defect"
    QUEUE_CONGESTION = "queue_congestion"
    CONFIGURATION_DRIFT = "configuration_drift"


class IncidentStage(StrEnum):
    DETECTED = "DETECTED"
    TRIAGING = "TRIAGING"
    INVESTIGATING = "INVESTIGATING"
    IMPACT_ASSESSING = "IMPACT_ASSESSING"
    REMEDIATION_PLANNING = "REMEDIATION_PLANNING"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    EXECUTING = "EXECUTING"
    REJUDGING = "REJUDGING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    PAUSED = "PAUSED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class IncidentSeverity(StrEnum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class SignalKind(StrEnum):
    METRIC = "metric"
    SUBMISSION = "submission"
    DEPLOYMENT = "deployment"
    COMPLAINT = "complaint"
    PACKAGE_CHANGE = "package_change"
    QUEUE = "queue"


class HypothesisState(StrEnum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ExperimentState(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"


class RejudgeBatchState(StrEnum):
    PLANNED = "PLANNED"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class VerificationStatus(StrEnum):
    RESOLVED = "RESOLVED"
    RESOLVED_WITH_WARNING = "RESOLVED_WITH_WARNING"
    ROLLBACK_REQUIRED = "ROLLBACK_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


class ApprovalLevel(StrEnum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    L5 = "L5"


class IncidentApprovalAction(StrEnum):
    APPROVE_REMEDIATION = "APPROVE_REMEDIATION"
    RUN_CANARY_REJUDGE = "RUN_CANARY_REJUDGE"
    RUN_BULK_REJUDGE = "RUN_BULK_REJUDGE"
    FREEZE_RESULTS = "FREEZE_RESULTS"
    SIMULATE_SCORE_WRITEBACK = "SIMULATE_SCORE_WRITEBACK"
    PREPARE_NOTIFICATION = "PREPARE_NOTIFICATION"
    CLOSE_INCIDENT = "CLOSE_INCIDENT"


class IncidentApprovalDecision(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"


class AgentRunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentRunEventType(StrEnum):
    RUN_CREATED = "RUN_CREATED"
    RUN_STARTED = "RUN_STARTED"
    ROUTE_DECISION = "ROUTE_DECISION"
    WORKER_STARTED = "WORKER_STARTED"
    WORKER_RESULT = "WORKER_RESULT"
    TOOL_RESULT = "TOOL_RESULT"
    STATE_TRANSITION = "STATE_TRANSITION"
    HUMAN_GATE = "HUMAN_GATE"
    RUN_PAUSED = "RUN_PAUSED"
    RUN_RESUMED = "RUN_RESUMED"
    FINAL_REPORT = "FINAL_REPORT"
    ERROR = "ERROR"


class IncidentProfile(BaseModel):
    incident_type: IncidentType
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=2_000)
    severity: IncidentSeverity = IncidentSeverity.SEV2
    playbook_id: str = Field(min_length=1, max_length=120)
    resource_scope: dict[str, list[str] | str | int | float | bool | None] = Field(
        default_factory=dict
    )
    source_systems: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)


class DiagnosticPlaybook(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    incident_type: IncidentType
    display_name: str
    signal_dimensions: list[str]
    hypothesis_templates: list[str]
    experiment_kinds: list[str]
    impact_policy: str
    remediation_actions: list[str]
    verification_checks: list[str]
    required_evidence: list[str]
    failure_policy: str


class IncidentSignal(BaseModel):
    id: str
    incident_id: str
    kind: SignalKind
    source: str
    observed_at: datetime
    summary: str
    dimensions: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class RootCauseHypothesis(BaseModel):
    id: str
    incident_id: str
    proposed_by: str
    category: str
    statement: str
    confidence: float = Field(ge=0, le=1)
    state: HypothesisState = HypothesisState.PROPOSED
    competing_hypothesis_ids: list[str] = Field(default_factory=list)
    required_experiment_kinds: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class IncidentExperiment(BaseModel):
    id: str
    incident_id: str
    hypothesis_ids: list[str]
    kind: str
    title: str
    control: dict[str, Any]
    treatment: dict[str, Any]
    success_criteria: dict[str, Any]
    state: ExperimentState = ExperimentState.PLANNED
    conclusion: str | None = None
    metrics: dict[str, float | int | str | bool | None] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ExperimentCandidate(BaseModel):
    kind: str
    title: str
    hypothesis_ids: list[str]
    dimensions: list[str]
    expected_discrimination: str
    evidence_refs: list[str] = Field(default_factory=list)


class ImpactAssessment(BaseModel):
    id: str
    incident_id: str
    policy: str
    candidate_ids: list[str] = Field(default_factory=list)
    submission_ids: list[str] = Field(default_factory=list)
    problem_ids: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    batches: list[str] = Field(default_factory=list)
    affected_candidate_count: int = Field(default=0, ge=0)
    affected_submission_count: int = Field(default=0, ge=0)
    projected_score_change_count: int = Field(default=0, ge=0)
    projected_advancement_change_count: int = Field(default=0, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_counts(self) -> ImpactAssessment:
        if self.candidate_ids and self.affected_candidate_count != len(self.candidate_ids):
            raise ValueError("affected_candidate_count must match candidate_ids")
        if self.submission_ids and self.affected_submission_count != len(self.submission_ids):
            raise ValueError("affected_submission_count must match submission_ids")
        return self


class RemediationStep(BaseModel):
    id: str
    action: str
    risk_level: ApprovalLevel
    preconditions: list[str]
    success_checks: list[str]
    stop_conditions: list[str]
    rollback_action: str


class RemediationPlan(BaseModel):
    id: str
    incident_id: str
    title: str
    steps: list[RemediationStep]
    approved_impact_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    revision: int = Field(default=1, ge=1)
    supersedes_plan_id: str | None = None
    reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class IncidentApprovalRecord(BaseModel):
    id: str
    incident_id: str
    action: IncidentApprovalAction
    level: ApprovalLevel
    decision: IncidentApprovalDecision = IncidentApprovalDecision.PENDING
    role_context: str
    actor: str
    target_id: str
    reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None


class RejudgeBatch(BaseModel):
    id: str
    incident_id: str
    plan_id: str
    sequence: int = Field(ge=0)
    kind: str
    idempotency_key: str
    submission_ids: list[str]
    state: RejudgeBatchState = RejudgeBatchState.PLANNED
    planned_count: int = Field(ge=0)
    completed_count: int = Field(default=0, ge=0)
    failed_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)
    attempt: int = Field(default=1, ge=1)
    supersedes_batch_id: str | None = None
    superseded_by_batch_id: str | None = None
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_progress(self) -> RejudgeBatch:
        accounted = self.completed_count + self.failed_count + self.skipped_count
        if accounted > self.planned_count:
            raise ValueError("accounted submissions cannot exceed planned_count")
        if self.submission_ids and self.planned_count != len(self.submission_ids):
            raise ValueError("planned_count must match submission_ids")
        return self


class ScoreChange(BaseModel):
    id: str
    incident_id: str
    candidate_id: str
    before_score: float
    after_score: float
    before_rank: int | None = Field(default=None, ge=1)
    after_rank: int | None = Field(default=None, ge=1)
    advancement_changed: bool = False
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class IncidentVerification(BaseModel):
    id: str
    incident_id: str
    status: VerificationStatus
    checks: dict[str, bool]
    coverage_rate: float = Field(ge=0, le=1)
    duplicate_rejudge_count: int = Field(default=0, ge=0)
    missing_rejudge_count: int = Field(default=0, ge=0)
    cross_scope_regression_count: int = Field(default=0, ge=0)
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class IncidentContext(BaseModel):
    incident_id: str = Field(min_length=1, max_length=120)
    profile: IncidentProfile
    stage: IncidentStage = IncidentStage.DETECTED
    signal_ids: list[str] = Field(default_factory=list)
    active_hypothesis_ids: list[str] = Field(default_factory=list)
    confirmed_root_cause_ids: list[str] = Field(default_factory=list)
    experiment_ids: list[str] = Field(default_factory=list)
    impact_assessment_id: str | None = None
    remediation_plan_ids: list[str] = Field(default_factory=list)
    approval_state: dict[str, IncidentApprovalDecision] = Field(default_factory=dict)
    rejudge_batch_ids: list[str] = Field(default_factory=list)
    score_change_ids: list[str] = Field(default_factory=list)
    verification_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    control_experiment_passed: bool = False
    canary_rejudge_passed: bool = False
    rejudge_complete: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class RouteOption(BaseModel):
    action: str
    worker: str
    tool: str | None = None
    arguments: dict[str, str | int | float | bool] = Field(default_factory=dict)
    expected_stages: list[IncidentStage]
    evidence_refs: list[str] = Field(default_factory=list)
    experiment_kind: str | None = None
    expected_result: str
    failure_action: str = "human_review"


class RouteDecision(BaseModel):
    action: str
    worker: str
    reason: str
    evidence_refs: list[str] = Field(default_factory=list)
    experiment_kind: str | None = None
    expected_result: str
    failure_action: str = "human_review"


class AgentRun(BaseModel):
    run_id: str
    task_id: str
    incident_id: str
    status: AgentRunStatus = AgentRunStatus.QUEUED
    orchestration_mode: str = "live_dynamic_routing"
    model: str = "deepseek-chat"
    max_model_responses: int = Field(default=20, ge=0, le=100)
    model_response_count: int = Field(default=0, ge=0)
    current_agent: str | None = None
    current_action: str | None = None
    last_event_sequence: int = Field(default=0, ge=0)
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class AgentRunEvent(BaseModel):
    id: str
    run_id: str
    incident_id: str
    sequence: int = Field(default=0, ge=0)
    event_type: AgentRunEventType
    agent: str
    action: str | None = None
    worker: str | None = None
    tool: str | None = None
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    before_stage: IncidentStage | None = None
    after_stage: IncidentStage | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
