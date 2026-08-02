from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.config import get_settings
from backend.app.dependencies import get_repository
from backend.app.domain import ApprovalRecord, PatchCandidate
from backend.app.runner import DockerRunner
from backend.app.services.demo_verifier import DemoAuditResult, DemoVerifier
from backend.app.services.evidence import EvidenceStore
from backend.app.services.patch_workflow import (
    PatchWorkflow,
    PatchWorkflowError,
    RegressionResult,
)
from backend.app.services.repository import SQLiteRepository
from backend.app.services.trace import TraceWriter

router = APIRouter(prefix="/workflow", tags=["workflow"])


class ApprovalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=100)
    reason: str | None = Field(default=None, max_length=1_000)


class RejectionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=1_000)


def _components(repository: SQLiteRepository) -> tuple[Path, PatchWorkflow]:
    settings = get_settings()
    workspace = Path.cwd()
    workflow = PatchWorkflow(
        repository=repository,
        workspaces_root=Path(settings.data_dir) / "workspaces",
    )
    return workspace, workflow


@router.post("/demo/audit", response_model=DemoAuditResult, status_code=status.HTTP_201_CREATED)
def audit_demo(repository: SQLiteRepository = Depends(get_repository)) -> DemoAuditResult:
    settings = get_settings()
    workspace = Path.cwd()
    verifier = DemoVerifier(
        runner=DockerRunner(
            packages_root=workspace / "demo",
            sessions_root=Path(settings.data_dir) / "runner-sessions",
        ),
        repository=repository,
        evidence_store=EvidenceStore(Path(settings.artifacts_dir)),
        trace_writer=TraceWriter(Path(settings.artifacts_dir)),
    )
    try:
        return verifier.audit(workspace / "demo" / "maximum_segment_score")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/demo/runs/{run_id}/patches", response_model=PatchCandidate)
def propose_demo_patch(
    run_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> PatchCandidate:
    workspace, workflow = _components(repository)
    try:
        return workflow.propose_demo_patch(
            run_id=run_id,
            original_root=workspace / "demo" / "maximum_segment_score",
        )
    except PatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/demo/patches/{patch_id}/approve", response_model=PatchCandidate)
def approve_demo_patch(
    patch_id: str,
    request: ApprovalRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> PatchCandidate:
    workspace, workflow = _components(repository)
    try:
        return workflow.approve_and_apply(
            patch_id=patch_id,
            original_root=workspace / "demo" / "maximum_segment_score",
            actor=request.actor,
            reason=request.reason,
        )
    except PatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/demo/patches/{patch_id}/reject", response_model=PatchCandidate)
def reject_demo_patch(
    patch_id: str,
    request: RejectionRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> PatchCandidate:
    _, workflow = _components(repository)
    try:
        return workflow.reject_patch(
            patch_id=patch_id,
            actor=request.actor,
            reason=request.reason,
        )
    except PatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/demo/patches/{patch_id}/regression", response_model=RegressionResult)
def regress_demo_patch(
    patch_id: str,
    repository: SQLiteRepository = Depends(get_repository),
) -> RegressionResult:
    _, workflow = _components(repository)
    try:
        return workflow.run_demo_regression(patch_id=patch_id)
    except PatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/demo/patches/{patch_id}/confirm", response_model=ApprovalRecord)
def confirm_demo_release(
    patch_id: str,
    request: ApprovalRequest,
    repository: SQLiteRepository = Depends(get_repository),
) -> ApprovalRecord:
    _, workflow = _components(repository)
    try:
        return workflow.confirm_release(
            patch_id=patch_id,
            actor=request.actor,
            reason=request.reason,
        )
    except PatchWorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
