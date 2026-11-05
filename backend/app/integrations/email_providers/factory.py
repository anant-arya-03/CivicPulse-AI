from functools import lru_cache

from app.core.config import get_settings
from app.integrations.email_providers.base import EmailProvider
from app.integrations.email_providers.mock_provider import MockEmailProvider


@lru_cache
def get_email_provider() -> EmailProvider:
    """FastAPI dependency. Only the simulated provider exists; tests override it."""
    return MockEmailProvider(get_settings().mock_email_scenario)
