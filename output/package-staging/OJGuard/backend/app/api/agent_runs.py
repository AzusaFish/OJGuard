from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.config import get_settings
from backend.app.dependencies import get_repository
from backend.app.domain import (
    AgentRun,
    AgentRunEvent,
    AgentRunEventType,
    AgentRunStatus,
    IncidentContext,
    IncidentType,
    RouteOption,
)
from backend.app.services.agent_routing import AgentRoutingPolicy
from backend.app.services.agentteams_dispatcher import (
    AgentTeamsDispatcher,
    AgentTeamsDispatcherError,
)
from backend.app.services.incident_workflow import IncidentWorkflowService
from backend.app.services.repository import SQLiteRepository

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


class CreateAgentRunRequest(BaseModel):
    incident_type: IncidentType = IncidentType.RUNTIME_REGRESSION
    incident_id: str | None = Field(default=None, min_length=1, max_length=120)
    task_id: str | None = Field(default=None, min_length=1, max_length=120)
    max_model_responses: int = Field(default=20, ge=0, le=100)


class LaunchAgentRunRequest(BaseModel):
    approval_actor: str = Field(default="demo-operator", min_length=1, max_length=120)
    timeout_minutes: int = Field(default=20, ge=1, le=120)


class AgentTeamsRuntimeStatus(BaseModel):
    ready: bool
    real_calls_enabled: bool
    api_key_configured: bool
    kubeconfig_present: bool
    launcher_present: bool
    python_present: bool
    gateway_reachable: bool
    message: str


class AgentRunLaunchResult(BaseModel):
    run_id: str
    pid: int
    status: str


class AgentRunSnapshot(BaseModel):
    run: AgentRun
    incident: IncidentContext
    legal_options: list[RouteOption]


def _snapshot(repository: SQLiteRepository, run: AgentRun) -> AgentRunSnapshot:
    incident = repository.get_incident(run.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return AgentRunSnapshot(
        run=run,
        incident=incident,
        legal_options=AgentRoutingPolicy(repository).legal_options(incident),
    )


@router.post("", response_model=AgentRunSnapshot, status_code=status.HTTP_201_CREATED)
def create_agent_run(
    request: CreateAgentRunRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> AgentRunSnapshot:
    task_id = request.task_id or f"OJGUARD-{uuid4().hex[:12].upper()}"
    if repository.get_agent_run_by_task(task_id) is not None:
        raise HTTPException(status_code=409, detail="task_id already exists")
    if request.incident_id:
        incident = repository.get_incident(request.incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="incident not found")
        if incident.stage.value != "TRIAGING":
            raise HTTPException(
                status_code=409,
                detail="AgentTeams can only start from a TRIAGING incident",
            )
        if (
            incident.confirmed_root_cause_ids
            or incident.impact_assessment_id
            or incident.remediation_plan_ids
        ):
            raise HTTPException(
                status_code=409,
                detail="incident contains precomputed decisions",
            )
        existing_run = repository.get_latest_agent_run_for_incident(incident.incident_id)
        if existing_run and existing_run.status not in {
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
        }:
            raise HTTPException(status_code=409, detail="incident already has an active AgentRun")
    else:
        incident = IncidentWorkflowService(repository).start_triage_demo(request.incident_type)
    run = AgentRun(
        run_id=f"ARUN-{uuid4().hex[:12].upper()}",
        task_id=task_id,
        incident_id=incident.incident_id,
        max_model_responses=request.max_model_responses,
    )
    repository.save_agent_run(run)
    repository.append_agent_run_event(
        AgentRunEvent(
            id=f"AEVT-{uuid4().hex[:12].upper()}",
            run_id=run.run_id,
            incident_id=incident.incident_id,
            event_type=AgentRunEventType.RUN_CREATED,
            agent="ojguard-runtime-control",
            action="bootstrap",
            summary="创建未预计算根因、影响或处置计划的 TRIAGING 事故",
            after_stage=incident.stage,
            evidence_refs=incident.signal_ids[:20],
        )
    )
    stored = repository.get_agent_run(run.run_id)
    if stored is None:
        raise HTTPException(status_code=500, detail="agent run was not persisted")
    return _snapshot(repository, stored)


@router.get("", response_model=list[AgentRun])
def list_agent_runs(
    limit: int = Query(default=100, ge=1, le=500),
    incident_id: str | None = Query(default=None, min_length=1, max_length=120),
    repository: SQLiteRepository = Depends(get_repository),
) -> list[AgentRun]:
    if incident_id:
        run = repository.get_latest_agent_run_for_incident(incident_id)
        return [run] if run else []
    return repository.list_agent_runs(limit=limit)


@router.get("/{run_id}/runtime", response_model=AgentTeamsRuntimeStatus)
def get_agentteams_runtime_status(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> AgentTeamsRuntimeStatus:
    if repository.get_agent_run(run_id) is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    readiness = AgentTeamsDispatcher(get_settings()).readiness()
    return AgentTeamsRuntimeStatus(**readiness.__dict__)


@router.post("/{run_id}/launch", response_model=AgentRunLaunchResult)
def launch_agent_run(
    run_id: str,
    request: LaunchAgentRunRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> AgentRunLaunchResult:
    run = repository.get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    if run.status != AgentRunStatus.QUEUED:
        raise HTTPException(status_code=409, detail="only a queued AgentRun can be launched")
    starting = run.model_copy(
        update={
            "status": AgentRunStatus.STARTING,
            "current_agent": "ojguard-runtime-control",
            "current_action": "launch_agentteams",
            "failure_reason": None,
            "updated_at": datetime.now(UTC),
        }
    )
    repository.save_agent_run(starting)
    try:
        launched = AgentTeamsDispatcher(get_settings()).launch(
            starting,
            approval_actor=request.approval_actor,
            timeout_minutes=request.timeout_minutes,
        )
    except AgentTeamsDispatcherError as exc:
        repository.save_agent_run(run)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentRunLaunchResult(run_id=run.run_id, pid=launched.pid, status="STARTING")


@router.post("/{run_id}/resume", response_model=AgentRunLaunchResult)
def resume_agent_run(
    run_id: str,
    request: LaunchAgentRunRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> AgentRunLaunchResult:
    run = repository.get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    if run.status not in {AgentRunStatus.FAILED, AgentRunStatus.PAUSED}:
        raise HTTPException(status_code=409, detail="only a failed or paused AgentRun can resume")
    previous = run.model_copy(deep=True)
    starting = run.model_copy(
        update={
            "status": AgentRunStatus.STARTING,
            "current_agent": "ojguard-runtime-control",
            "current_action": "resume_agentteams",
            "failure_reason": None,
            "completed_at": None,
            "updated_at": datetime.now(UTC),
        }
    )
    repository.save_agent_run(starting)
    try:
        launched = AgentTeamsDispatcher(get_settings()).launch(
            starting,
            approval_actor=request.approval_actor,
            timeout_minutes=request.timeout_minutes,
            resume=True,
        )
    except AgentTeamsDispatcherError as exc:
        repository.save_agent_run(previous)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return AgentRunLaunchResult(run_id=run.run_id, pid=launched.pid, status="STARTING")


@router.get("/{run_id}", response_model=AgentRunSnapshot)
def get_agent_run(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> AgentRunSnapshot:
    run = repository.get_agent_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return _snapshot(repository, run)


@router.get("/{run_id}/events", response_model=list[AgentRunEvent])
def get_agent_run_events(
    run_id: str,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2_000),
    repository: SQLiteRepository = Depends(get_repository),
) -> list[AgentRunEvent]:
    if repository.get_agent_run(run_id) is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return repository.list_agent_run_events(
        run_id,
        after_sequence=after_sequence,
        limit=limit,
    )


@router.get("/{run_id}/stream")
async def stream_agent_run_events(
    run_id: str,
    request: Request,
    after_sequence: int = Query(default=0, ge=0),
    repository: SQLiteRepository = Depends(get_repository),
) -> StreamingResponse:
    if repository.get_agent_run(run_id) is None:
        raise HTTPException(status_code=404, detail="agent run not found")

    async def event_stream():
        cursor = after_sequence
        last_heartbeat = datetime.now(UTC)
        while not await request.is_disconnected():
            events = repository.list_agent_run_events(
                run_id,
                after_sequence=cursor,
                limit=500,
            )
            for event in events:
                cursor = event.sequence
                payload = json.dumps(
                    event.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"id: {event.sequence}\nevent: {event.event_type.value}\ndata: {payload}\n\n"
            now = datetime.now(UTC)
            if (now - last_heartbeat).total_seconds() >= 15:
                yield f": heartbeat {now.isoformat()}\n\n"
                last_heartbeat = now
            run = repository.get_agent_run(run_id)
            if run is None or (run.completed_at is not None and not events):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
