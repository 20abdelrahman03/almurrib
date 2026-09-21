"""Provider registry tests: definitions stay complete and routable."""

import pytest

from almurrib.core.errors import ProviderError
from almurrib.core.provider import ProviderConfig
from almurrib.providers.cohere import CohereProvider
from almurrib.providers.factory import build_provider
from almurrib.providers.openai_compat import OpenAICompatibleProvider
from almurrib.providers.registry import PROVIDERS, get_definition, list_definitions


def _config(provider: str) -> ProviderConfig:
    return ProviderConfig(
        provider=provider, model="m", base_url="https://x.test/v1", api_key="k"
    )


def test_every_definition_is_complete():
    for definition in PROVIDERS.values():
        assert definition.id
        assert definition.display_name
        assert definition.protocol in ("openai_chat", "cohere", "anthropic", "argos")
        if definition.id == "argos":
            assert definition.base_url == "local"  # no endpoint by design
        else:
            assert definition.base_url.startswith(("https://", "http://"))
            assert definition.models_path.startswith("/")
        assert definition.discovery in ("openai", "cohere", "none", "argos")
        assert definition.json_object in ("yes", "no", "model-dependent")


def test_required_ecosystem_ids_present():
    for wanted in (
        "openrouter", "tokenrouter", "agentrouter", "openai", "cohere",
        "nim", "ollama", "llamacpp", "vllm", "groq", "deepseek",
        "openai_compat",
    ):
        assert wanted in PROVIDERS, wanted


def test_legacy_openai_compat_resolves():
    """Early configs (provider=openai_compat) must keep working + discover."""
    from almurrib.providers.registry import get_definition

    definition = get_definition("openai_compat")
    assert definition is not None
    assert definition.protocol == "openai_chat"
    assert definition.discovery == "openai"


def test_main_providers_ship_fallback_models():
    for wanted in ("openrouter", "openai", "cohere", "ollama", "groq",
                   "deepseek", "gemini", "mistral"):
        models = PROVIDERS[wanted].fallback_models
        assert models, wanted
        assert all(isinstance(m, str) and m.strip() for m in models)


def test_verified_definitions_are_openai_compatible_or_native():
    verified = [d for d in PROVIDERS.values() if d.verified]
    assert {"openrouter", "tokenrouter", "agentrouter", "cohere", "nim",
            "ollama", "groq", "deepseek", "deepinfra", "openai"} <= {
        d.id for d in verified
    }


def test_factory_routes_generic_ids():
    for provider_id in ("openrouter", "openai", "ollama", "groq", "nim",
                        "tokenrouter", "agentrouter", "openai_compat"):
        assert isinstance(build_provider(_config(provider_id)),
                          OpenAICompatibleProvider)


def test_factory_routes_cohere():
    assert isinstance(build_provider(_config("cohere")), CohereProvider)


def test_factory_rejects_unknown():
    with pytest.raises(ProviderError):
        build_provider(_config("nope-not-a-provider"))


def test_list_definitions_sorted_and_filterable():
    all_defs = list_definitions()
    assert [d.display_name.lower() for d in all_defs] == sorted(
        d.display_name.lower() for d in all_defs
    )
    local = {d.id for d in list_definitions(local_only=True)}
    assert {"ollama", "llamacpp", "vllm", "nim"} <= local
    assert "openai" not in local


def test_get_definition_unknown_returns_none():
    assert get_definition("missing") is None
