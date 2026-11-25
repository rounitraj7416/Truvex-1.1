"""Factory selecting the configured AI provider."""

from __future__ import annotations

from app.core.config import get_settings
from app.trust_engine.ai_provider import AIProvider, ProviderConfigurationError
from app.trust_engine.detectifai_provider import DetectifAIProvider
from app.trust_engine.mock_provider import MockAIProvider


def get_ai_provider() -> AIProvider:
    """Instantiate the configured AI provider from settings.AI_PROVIDER."""
    provider_key = get_settings().AI_PROVIDER.strip().lower()
    if provider_key == "mock":
        return MockAIProvider()
    if provider_key == "detectifai":
        provider = DetectifAIProvider()
        # Validate configuration early so misconfigurations fail cleanly.
        try:
            provider._ensure_configured()
        except ProviderConfigurationError:
            raise
        return provider
    raise ProviderConfigurationError(
        f"Unsupported AI_PROVIDER '{provider_key}'. Supported values: 'mock', 'detectifai'."
    )
