from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from backend.app.config import Settings, get_settings

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/health")
def rag_health(settings: Settings = Depends(get_settings)) -> JSONResponse:
    if not settings.rag_enabled:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "disabled",
                "code": "RAG_DISABLED",
                "message": "RAG contract is reserved but the provider is disabled for the initial round.",
                "port": settings.rag_port,
            },
        )
    return JSONResponse(content={"status": "ok", "provider": "not_configured"})
