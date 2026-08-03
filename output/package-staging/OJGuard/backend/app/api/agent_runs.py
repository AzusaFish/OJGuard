from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.dependencies import get_repository
from backend.app.domain import (
    AgentRun,
    AgentRunEvent,
    AgentRunEventType,
    IncidentContext,
    IncidentType,
    RouteOption,
)
from backend.app.services.agent_routing import AgentRoutingPolicy
from backend.app.services.incident_workflow import IncidentWorkflowService
from backend.app.services.repository import SQLiteRepository

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


class CreateAgentRunRequest(BaseModel):
    incident_type: IncidentType = IncidentType.RUNTIME_REGRESSION
    task_id: str | None = Field(default=None, min_length=1, max_length=120)
    max_model_responses: int = Field(default=20, ge=0, le=100)


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
    repository: SQLiteRepository = Depends(get_repository),
) -> list[AgentRun]:
    return repository.list_agent_runs(limit=limit)


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
