"""Application settings, loaded from environment variables and the repository-root `.env` file.

Every configurable value lives here so the rest of the code never reads `os.environ` directly.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] is the repository root
REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"

_INSECURE_DEFAULT_SECRET = "change-me-to-a-long-random-string"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env also holds settings for later milestones
    )

    # App
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    secret_key: str = _INSECURE_DEFAULT_SECRET

    # Database
    database_url: str
    test_database_url: str | None = None

    # Auth & security
    session_cookie_name: str = "cp_session"
    csrf_cookie_name: str = "cp_csrf"
    session_ttl_hours: int = 168
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000"  # comma-separated
    rate_limit_enabled: bool = True

    # File storage
    storage_backend: Literal["local"] = "local"
    local_storage_dir: str = "./storage"  # relative paths are relative to backend/
    max_upload_mb: int = 10

    # Geocoding (address search for the report form)
    geocoder: Literal["mock", "nominatim"] = "mock"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = ""

    # AI (see app/integrations/ai_providers/)
    ai_provider: Literal["mock", "anthropic"] = "mock"
    mock_ai_scenario: Literal[
        "pothole", "streetlight", "garbage", "not_civic", "failure", "invalid"
    ] = "pothole"
    # What the mock says when comparing before/after photos (it doesn't look at them).
    mock_ai_resolution: Literal[
        "resolved", "not_resolved", "partial", "unsure", "different_place"
    ] = "resolved"
    ai_model: str = "claude-opus-5-5"
    ai_effort: Literal["low", "medium", "high"] = "medium"
    ai_timeout_seconds: int = 90
    # SecretStr keeps the key out of logs, error messages, and repr() output.
    anthropic_api_key: SecretStr | None = None

    # Email (complaint submission). Only a simulated provider exists: nothing is ever sent to a
    # real department. success | failure (every send fails) | flaky (first attempt fails).
    email_provider: Literal["mock"] = "mock"
    mock_email_scenario: Literal["success", "failure", "flaky"] = "success"
    email_from_address: str = "civicpulse-demo@example.com"
    # A future real provider must also require this to be true (see communications/service.py).
    allow_real_submissions: bool = False

    # Monitoring & follow-ups (see docs/workflows.md section 5). The worker only DRAFTS reminders;
    # the citizen approves every one, and at most `followup_max_count` are ever sent.
    followup_first_after_days: int = Field(7, ge=1, le=90)  # if the department lists no timeline
    followup_interval_days: int = Field(7, ge=1, le=90)
    followup_max_count: int = Field(2, ge=0, le=5)
    scheduler_max_attempts: int = Field(3, ge=1, le=10)  # retries for a failing scheduled action
    # Development/demo only: simulated department replies and "skip ahead in time".
    enable_simulation: bool = False

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _empty_key_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def local_storage_path(self) -> Path:
        path = Path(self.local_storage_dir)
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @model_validator(mode="after")
    def _check_nominatim_identity(self) -> "Settings":
        # Nominatim's usage policy requires an identifying User-Agent with a real contact.
        ua = self.nominatim_user_agent
        if self.geocoder == "nominatim" and (not ua or "example.com" in ua):
            raise ValueError(
                "GEOCODER=nominatim needs NOMINATIM_USER_AGENT set to your app name and a real "
                "contact email, e.g. 'CivicPulseAI-student-project (contact: you@your-domain)'."
            )
        return self

    @model_validator(mode="after")
    def _check_ai_credentials(self) -> "Settings":
        if self.ai_provider == "anthropic" and self.anthropic_api_key is None:
            raise ValueError("AI_PROVIDER=anthropic needs ANTHROPIC_API_KEY to be set.")
        return self

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        if self.is_production:
            if self.secret_key == _INSECURE_DEFAULT_SECRET or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be set to a long random value in production.")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production (HTTPS only).")
            if self.enable_simulation:
                raise ValueError("ENABLE_SIMULATION must be false in production.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance (read once per process)."""
    return Settings()  # type: ignore[call-arg]  # database_url comes from the environment
