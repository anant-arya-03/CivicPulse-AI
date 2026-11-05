from functools import lru_cache

from app.core.config import get_settings
from app.integrations.storage.base import StorageService
from app.integrations.storage.local_storage import LocalStorage


@lru_cache
def get_storage() -> StorageService:
    """FastAPI dependency returning the configured storage backend (tests override it)."""
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.local_storage_path)
    raise ValueError(f"Unknown STORAGE_BACKEND: {settings.storage_backend}")
