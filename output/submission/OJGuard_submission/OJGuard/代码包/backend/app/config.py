from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "OJGuard"
    app_env: str = "development"
    api_prefix: str = "/api/v1"

    data_dir: Path = Path("data")
    artifacts_dir: Path = Path("artifacts")

    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    llm_real_calls_enabled: bool = False
    llm_budget_warning_cny: float = Field(default=6.0, ge=0)
    llm_budget_stop_cny: float = Field(default=8.0, gt=0)

    rag_enabled: bool = False
    rag_port: int = Field(default=8010, ge=1024, le=65535)
    rag_api_prefix: str = "/api/v1/rag"

    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8020, ge=1024, le=65535)

    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def ensure_runtime_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
