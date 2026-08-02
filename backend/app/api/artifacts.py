from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_repository
from backend.app.domain import AgentEvent, ApprovalRecord, Evidence, Finding, PatchCandidate
from backend.app.services.repository import SQLiteRepository

router = APIRouter(prefix="/runs/{run_id}", tags=["artifacts"])


def ensure_run(run_id: str, repository: SQLiteRepository) -> None:
    if repository.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")


@router.get("/events")
def list_events(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> list[AgentEvent]:
    ensure_run(run_id, repository)
    return repository.list_events(run_id)


@router.get("/findings")
def list_findings(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> list[Finding]:
    ensure_run(run_id, repository)
    return repository.list_findings(run_id)


@router.get("/evidence")
def list_evidence(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> list[Evidence]:
    ensure_run(run_id, repository)
    return repository.list_evidence(run_id)


@router.get("/approvals")
def list_approvals(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> list[ApprovalRecord]:
    ensure_run(run_id, repository)
    return repository.list_approvals(run_id)


@router.get("/patches")
def list_patches(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> list[PatchCandidate]:
    ensure_run(run_id, repository)
    return repository.list_patches(run_id)
