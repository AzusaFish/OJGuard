from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.app.dependencies import get_repository
from backend.app.domain import (
    DiagnosticPlaybook,
    ImpactAssessment,
    IncidentApprovalAction,
    IncidentApprovalDecision,
    IncidentApprovalRecord,
    IncidentContext,
    IncidentExperiment,
    IncidentProfile,
    IncidentSeverity,
    IncidentSignal,
    IncidentStage,
    IncidentType,
    IncidentVerification,
    RejudgeBatch,
    RemediationPlan,
    RootCauseHypothesis,
    ScoreChange,
    SignalKind,
)
from backend.app.services.incident_reporting import (
    IncidentReport,
    build_incident_report,
    render_report_html,
)
from backend.app.services.incident_state_machine import (
    InvalidIncidentTransitionError,
    transition_incident,
)
from backend.app.services.incident_workflow import (
    IncidentWorkflowError,
    IncidentWorkflowService,
)
from backend.app.services.playbooks import default_playbook_for, get_playbook, list_playbooks
from backend.app.services.repository import SQLiteRepository

router = APIRouter(prefix="/incidents", tags=["incidents"])


class CreateIncidentRequest(BaseModel):
    incident_type: IncidentType
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=2_000)
    severity: IncidentSeverity = IncidentSeverity.SEV2
    playbook_id: str | None = Field(default=None, max_length=120)
    resource_scope: dict[str, list[str] | str | int | float | bool | None] = Field(
        default_factory=dict
    )
    source_systems: list[str] = Field(default_factory=list)


class IncidentTransitionRequest(BaseModel):
    target: IncidentStage


class CreateSignalRequest(BaseModel):
    kind: SignalKind
    source: str = Field(min_length=1, max_length=120)
    observed_at: datetime
    summary: str = Field(min_length=1, max_length=1_000)
    dimensions: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class IncidentApprovalRequest(BaseModel):
    action: IncidentApprovalAction
    role_context: str = Field(min_length=1, max_length=80)
    actor: str = Field(min_length=1, max_length=120)
    decision: IncidentApprovalDecision
    reason: str | None = Field(default=None, max_length=1_000)


class IncidentWorkspace(BaseModel):
    incident: IncidentContext
    playbook: DiagnosticPlaybook
    signals: list[IncidentSignal]
    hypotheses: list[RootCauseHypothesis]
    experiments: list[IncidentExperiment]
    impacts: list[ImpactAssessment]
    remediation_plans: list[RemediationPlan]
    approvals: list[IncidentApprovalRecord]
    rejudge_batches: list[RejudgeBatch]
    score_changes: list[ScoreChange]
    verifications: list[IncidentVerification]


def _get_incident_or_404(repository: SQLiteRepository, incident_id: str) -> IncidentContext:
    incident = repository.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


def _workspace(repository: SQLiteRepository, incident: IncidentContext) -> IncidentWorkspace:
    incident_id = incident.incident_id
    return IncidentWorkspace(
        incident=incident,
        playbook=get_playbook(incident.profile.playbook_id),
        signals=repository.list_incident_signals(incident_id),
        hypotheses=repository.list_root_cause_hypotheses(incident_id),
        experiments=repository.list_incident_experiments(incident_id),
        impacts=repository.list_impact_assessments(incident_id),
        remediation_plans=repository.list_remediation_plans(incident_id),
        approvals=repository.list_incident_approvals(incident_id),
        rejudge_batches=repository.list_rejudge_batches(incident_id),
        score_changes=repository.list_score_changes(incident_id),
        verifications=repository.list_incident_verifications(incident_id),
    )


def _workflow_call(operation: object) -> object:
    try:
        return operation()  # type: ignore[operator]
    except (IncidentWorkflowError, InvalidIncidentTransitionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/playbooks", response_model=list[DiagnosticPlaybook])
def get_incident_playbooks() -> list[DiagnosticPlaybook]:
    return list_playbooks()


@router.post(
    "/demo/{incident_type}",
    response_model=IncidentWorkspace,
    status_code=status.HTTP_201_CREATED,
)
def prepare_demo_incident(
    incident_type: IncidentType,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentWorkspace:
    try:
        incident = IncidentWorkflowService(repository).prepare_demo(incident_type)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _workspace(repository, incident)


@router.post("", response_model=IncidentContext, status_code=status.HTTP_201_CREATED)
def create_incident(
    request: CreateIncidentRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentContext:
    try:
        playbook = (
            get_playbook(request.playbook_id)
            if request.playbook_id
            else default_playbook_for(request.incident_type)
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if playbook.incident_type != request.incident_type:
        raise HTTPException(status_code=422, detail="playbook does not match incident_type")

    incident_id = f"INC-{uuid4().hex[:10].upper()}"
    profile = IncidentProfile(
        incident_type=request.incident_type,
        title=request.title,
        summary=request.summary,
        severity=request.severity,
        playbook_id=playbook.id,
        resource_scope=request.resource_scope,
        source_systems=request.source_systems,
        dimensions=playbook.signal_dimensions,
    )
    incident = IncidentContext(incident_id=incident_id, profile=profile)
    repository.save_incident(incident)
    return incident


@router.get("", response_model=list[IncidentContext])
def get_incidents(
    limit: int = 100,
    repository: SQLiteRepository = Depends(get_repository),
) -> list[IncidentContext]:
    return repository.list_incidents(limit=min(max(limit, 1), 500))


@router.get("/{incident_id}", response_model=IncidentContext)
def get_incident(
    incident_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentContext:
    return _get_incident_or_404(repository, incident_id)


@router.get("/{incident_id}/workspace", response_model=IncidentWorkspace)
def get_incident_workspace(
    incident_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentWorkspace:
    incident = _get_incident_or_404(repository, incident_id)
    return _workspace(repository, incident)


@router.get("/{incident_id}/report", response_model=IncidentReport)
def get_incident_report(
    incident_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentReport:
    incident = _get_incident_or_404(repository, incident_id)
    return build_incident_report(repository, incident)


@router.get("/{incident_id}/report.html", response_class=HTMLResponse)
def get_incident_report_html(
    incident_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> HTMLResponse:
    incident = _get_incident_or_404(repository, incident_id)
    report = build_incident_report(repository, incident)
    return HTMLResponse(render_report_html(report))


@router.post("/{incident_id}/signals", response_model=IncidentSignal)
def add_incident_signal(
    incident_id: str,
    request: CreateSignalRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentSignal:
    incident = _get_incident_or_404(repository, incident_id)
    signal = IncidentSignal(
        id=f"SIG-{uuid4().hex[:10].upper()}",
        incident_id=incident_id,
        **request.model_dump(),
    )
    repository.save_incident_signal(signal)
    updated = incident.model_copy(deep=True)
    if signal.id not in updated.signal_ids:
        updated.signal_ids.append(signal.id)
    repository.save_incident(updated)
    return signal


@router.post("/{incident_id}/transition", response_model=IncidentContext)
def transition_incident_stage(
    incident_id: str,
    request: IncidentTransitionRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentContext:
    incident = _get_incident_or_404(repository, incident_id)
    try:
        updated = transition_incident(incident, request.target)
    except InvalidIncidentTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    repository.save_incident(updated)
    return updated


@router.post("/{incident_id}/approvals", response_model=IncidentApprovalRecord)
def decide_incident_approval(
    incident_id: str,
    request: IncidentApprovalRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentApprovalRecord:
    workflow = IncidentWorkflowService(repository)
    return _workflow_call(
        lambda: workflow.record_approval(
            incident_id,
            action=request.action,
            role_context=request.role_context,
            actor=request.actor,
            decision=request.decision,
            reason=request.reason,
        )
    )  # type: ignore[return-value]


@router.post("/{incident_id}/execute/control-canary", response_model=IncidentWorkspace)
def execute_control_canary(
    incident_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentWorkspace:
    workflow = IncidentWorkflowService(repository)
    incident = _workflow_call(lambda: workflow.execute_control_and_canary(incident_id))
    return _workspace(repository, incident)  # type: ignore[arg-type]


@router.post("/{incident_id}/execute/bulk", response_model=IncidentWorkspace)
def execute_bulk_rejudge(
    incident_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentWorkspace:
    workflow = IncidentWorkflowService(repository)
    incident = _workflow_call(lambda: workflow.execute_bulk(incident_id))
    return _workspace(repository, incident)  # type: ignore[arg-type]


@router.post("/{incident_id}/verify", response_model=IncidentWorkspace)
def verify_incident(
    incident_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentWorkspace:
    workflow = IncidentWorkflowService(repository)
    incident = _workflow_call(lambda: workflow.verify(incident_id))
    return _workspace(repository, incident)  # type: ignore[arg-type]


@router.post("/{incident_id}/close", response_model=IncidentWorkspace)
def close_incident(
    incident_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> IncidentWorkspace:
    workflow = IncidentWorkflowService(repository)
    incident = _workflow_call(lambda: workflow.close(incident_id))
    return _workspace(repository, incident)  # type: ignore[arg-type]
