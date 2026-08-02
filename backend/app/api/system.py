import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from backend.app.config import Settings, get_settings
from backend.app.dependencies import get_repository
from backend.app.services.repository import SQLiteRepository

router = APIRouter(tags=["system"])


def _preview_content(value: object) -> object:
    if isinstance(value, str) and len(value) > 2_000:
        omitted = len(value) - 2_000
        return f"{value[:2_000]}\n… [preview truncated; {omitted} characters remain in artifact]"
    if isinstance(value, list):
        return [_preview_content(item) for item in value[:200]]
    if isinstance(value, dict):
        return {str(key): _preview_content(item) for key, item in value.items()}
    return value


@router.get("/system")
def system_info(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "environment": settings.app_env,
        "provider": "deepseek",
        "model": settings.deepseek_model,
        "llm_calls_enabled": settings.llm_real_calls_enabled,
        "budget_warning_cny": settings.llm_budget_warning_cny,
        "budget_stop_cny": settings.llm_budget_stop_cny,
        "rag": {"enabled": settings.rag_enabled, "port": settings.rag_port},
        "mcp": {"host": settings.mcp_host, "port": settings.mcp_port, "path": "/mcp"},
        "agentteams": {
            "version": "v1.2.0",
            "team": "ojguard-audit-team",
            "deployment": "kubernetes-kind",
            "worker_backend": "k8s",
            "host_socket_exposed": False,
            "element_url": "http://127.0.0.1:18080",
        },
    }


@router.get("/benchmark/report")
def benchmark_report() -> JSONResponse:
    path = Path.cwd() / "benchmark" / "results" / "baseline_report.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="benchmark report has not been generated")
    return JSONResponse(content=json.loads(path.read_text(encoding="utf-8")))


@router.get("/runs/{run_id}/evidence/{evidence_id}/content")
def evidence_content(
    run_id: str,
    evidence_id: str,
    repository: SQLiteRepository = Depends(get_repository),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    evidence = next(
        (item for item in repository.list_evidence(run_id) if item.id == evidence_id), None
    )
    if evidence is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    root = Path(settings.artifacts_dir).resolve()
    target = (root / evidence.artifact_path).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=409, detail="evidence artifact is missing or unsafe")
    payload = target.read_bytes()
    if len(payload) > 1_048_576:
        raise HTTPException(status_code=413, detail="evidence artifact exceeds preview limit")
    try:
        content: object = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        content = payload.decode("utf-8", errors="replace")
    return JSONResponse(
        content={
            "evidence_id": evidence.id,
            "sha256": evidence.sha256,
            "verified": evidence.sha256 == hashlib.sha256(payload).hexdigest(),
            "content": _preview_content(content),
        }
    )
