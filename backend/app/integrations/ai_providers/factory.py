from functools import lru_cache

from app.core.config import get_settings
from app.integrations.ai_providers.anthropic_provider import AnthropicProvider
from app.integrations.ai_providers.base import AIProvider
from app.integrations.ai_providers.mock_provider import MockAIProvider


@lru_cache
def get_ai_provider() -> AIProvider:
    """FastAPI dependency returning the configured AI provider (AI_PROVIDER=mock|anthropic).
    Tests override it with a MockAIProvider for the scenario they need."""
    settings = get_settings()
    if settings.ai_provider == "anthropic":
        assert settings.anthropic_api_key is not None  # guaranteed by Settings validation
        return AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.ai_model,
            effort=settings.ai_effort,
            timeout_seconds=settings.ai_timeout_seconds,
        )
    return MockAIProvider(settings.mock_ai_scenario, settings.mock_ai_resolution)
