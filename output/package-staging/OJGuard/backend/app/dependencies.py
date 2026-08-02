from functools import lru_cache
from pathlib import Path

from backend.app.config import get_settings
from backend.app.services.repository import SQLiteRepository


@lru_cache
def get_repository() -> SQLiteRepository:
    settings = get_settings()
    return SQLiteRepository(Path(settings.data_dir) / "ojguard.sqlite3")
