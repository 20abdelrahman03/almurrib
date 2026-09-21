"""Provider factory: turn configuration into a TranslationProvider.

Routing is registry-driven: ``openai_chat`` protocol ids share the generic
transport, ``cohere`` gets its native adapter. The legacy ``openai_compat``
id keeps working (generic transport). This stays the ONLY place that maps
provider names to implementations.
"""

from __future__ import annotations

from almurrib.core.errors import ProviderError
from almurrib.core.provider import ProviderConfig, TranslationProvider
from almurrib.providers.cohere import CohereProvider
from almurrib.providers.openai_compat import OpenAICompatibleProvider
from almurrib.providers.registry import PROVIDERS, get_definition


def build_provider(config: ProviderConfig) -> TranslationProvider:
    if config.provider == "openai_compat":
        # Legacy id from early Phase 1: the generic transport.
        return OpenAICompatibleProvider(config)
    if config.provider == "fake":
        from almurrib.providers.fake import FakeProvider

        return FakeProvider(config)
    definition = get_definition(config.provider)
    if definition is None:
        raise ProviderError(
            f"unknown provider '{config.provider}'",
            hint=f"available: {', '.join(sorted(PROVIDERS))}. "
            "Any OpenAI-compatible API can also use 'openai_compat'.",
        )
    if definition.protocol == "cohere":
        return CohereProvider(config)
    if definition.protocol == "argos":
        from almurrib.providers.argos import ArgosProvider

        return ArgosProvider(config)
    if definition.protocol == "openai_chat":
        return OpenAICompatibleProvider(config)
    raise ProviderError(
        f"provider '{config.provider}' uses protocol '{definition.protocol}', "
        "which has no adapter yet",
        hint=(definition.notes or "use a router definition instead."),
    )
