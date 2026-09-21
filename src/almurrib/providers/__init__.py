"""Concrete translation providers.

The Core never imports from here directly; the CLI/factory wires providers
in. Adding a provider = implement TranslationProvider + register it in
``factory.py``. No core changes needed.
"""

from almurrib.providers.catalog import (
    RefreshResult,
    cached_models,
    refresh_models,
    static_models,
    store_models,
)
from almurrib.providers.cohere import CohereProvider
from almurrib.providers.discovery import (
    SOURCE_LITELLM,
    SOURCE_LIVE,
    SOURCE_MODELS_DEV,
    SOURCE_STATIC,
    ModelInfo,
    fetch_models,
)
from almurrib.providers.factory import build_provider
from almurrib.providers.openai_compat import OpenAICompatibleProvider
from almurrib.providers.registry import (
    PROVIDERS,
    ProviderDefinition,
    discovery_strategy,
    get_definition,
    list_definitions,
)

__all__ = [
    "CohereProvider",
    "ModelInfo",
    "OpenAICompatibleProvider",
    "PROVIDERS",
    "ProviderDefinition",
    "RefreshResult",
    "build_provider",
    "cached_models",
    "discovery_strategy",
    "fetch_models",
    "get_definition",
    "list_definitions",
    "refresh_models",
    "static_models",
    "store_models",
    "SOURCE_LITELLM",
    "SOURCE_LIVE",
    "SOURCE_MODELS_DEV",
    "SOURCE_STATIC",
]
