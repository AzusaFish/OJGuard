from fastapi import APIRouter, Depends

from backend.app.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "model_provider": "deepseek",
        "model": settings.deepseek_model,
        "real_llm_calls_enabled": settings.llm_real_calls_enabled,
        "rag_enabled": settings.rag_enabled,
    }
