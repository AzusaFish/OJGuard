from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.app.config import get_settings
from backend.app.dependencies import get_repository
from backend.app.domain import RunBudgets, RunStage, TaskContext
from backend.app.domain.package import PackageManifest
from backend.app.services.package_ingest import PackageIngestError, PackageIngestor
from backend.app.services.repository import SQLiteRepository
from backend.app.services.state_machine import InvalidTransitionError, transition

router = APIRouter(prefix="/runs", tags=["runs"])


class CreateRunRequest(BaseModel):
    package_id: str = Field(min_length=1, max_length=100)
    budgets: RunBudgets = Field(default_factory=RunBudgets)


class TransitionRequest(BaseModel):
    target: RunStage


@router.post("/packages", response_model=PackageManifest, status_code=status.HTTP_201_CREATED)
async def upload_package(
    package_id: str = Form(..., min_length=1, max_length=100),
    archive: UploadFile = File(...),
) -> PackageManifest:
    settings = get_settings()
    ingestor = PackageIngestor(Path(settings.data_dir) / "packages")
    payload = await archive.read()
    try:
        return ingestor.ingest_zip(
            package_id=package_id,
            filename=archive.filename or "package.zip",
            payload=payload,
        )
    except PackageIngestError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_run(
    request: CreateRunRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> TaskContext:
    suffix = uuid4().hex[:10].upper()
    run_id = f"RUN-{suffix}"
    context = TaskContext(
        task_id=f"TASK-{suffix}",
        package_id=request.package_id,
        run_id=run_id,
        budgets=request.budgets,
    )
    repository.save_run(context)
    return context


@router.get("")
def list_runs(
    limit: int = 100,
    repository: SQLiteRepository = Depends(get_repository),
) -> list[TaskContext]:
    return repository.list_runs(limit=min(max(limit, 1), 500))


@router.get("/{run_id}")
def get_run(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> TaskContext:
    context = repository.get_run(run_id)
    if context is None:
        raise HTTPException(status_code=404, detail="run not found")
    return context


@router.post("/{run_id}/transition")
def transition_run(
    run_id: str,
    request: TransitionRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> TaskContext:
    context = repository.get_run(run_id)
    if context is None:
        raise HTTPException(status_code=404, detail="run not found")
    try:
        updated = transition(context, request.target)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    repository.save_run(updated)
    return updated
