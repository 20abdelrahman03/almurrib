"""Provider factory: turn configuration into a TranslationProvider.

This is the ONLY place that maps provider names to implementations, so the
Core and pipeline never hardcode a provider. Registering a new provider
here is the entire integration cost.
"""

from __future__ import annotations

from almurrib.core.errors import ProviderError
from almurrib.core.provider import ProviderConfig, TranslationProvider
from almurrib.providers.openai_compat import OpenAICompatibleProvider

# provider name -> builder. "fake" is registered for tests/demos offline.
_BUILDERS = {
    "openai_compat": OpenAICompatibleProvider,
}

# Well-known OpenAI-compatible endpoints (convenience presets; all BYO-key).
PRESETS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "kimi": "https://api.moonshot.ai/v1",
    "llamacpp": "http://localhost:8080/v1",  # future local path
}


def build_provider(config: ProviderConfig) -> TranslationProvider:
    builder = _BUILDERS.get(config.provider)
    if builder is None:
        raise ProviderError(
            f"unknown provider '{config.provider}'",
            hint=f"available: {', '.join(sorted(_BUILDERS))}. "
            "OpenAI-compatible APIs can all use 'openai_compat'.",
        )
    return builder(config)


def preset_base_url(name: str) -> str | None:
    return PRESETS.get(name)
