"""Concrete translation providers.

The Core never imports from here directly; the CLI/factory wires providers
in. Adding a provider = implement TranslationProvider + register it in
``factory.py``. No core changes needed.
"""

from almurrib.providers.llamacpp import (
    LlamaServer,
    health_ok,
    start_server,
    wait_ready,
)
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
    SOURCE_LOCAL,
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

# Heavy optional providers stay lazy so imports (and PyInstaller) never
# pull torch/Unity stacks unless actually used.
_LAZY_PROVIDERS = {
    "ArgosProvider": "almurrib.providers.argos",
    "installed_models": "almurrib.providers.argos",
}


def __getattr__(name: str):
    if name in _LAZY_PROVIDERS:
        import importlib

        module = importlib.import_module(_LAZY_PROVIDERS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ArgosProvider",
    "CohereProvider",
    "LlamaServer",
    "health_ok",
    "installed_models",
    "start_server",
    "wait_ready",
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
    "SOURCE_LOCAL",
    "SOURCE_MODELS_DEV",
    "SOURCE_STATIC",
]
