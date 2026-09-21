"""Model catalog tests: live first, external fallback, static last.

All HTTP is mocked — the default suite stays offline. No keys in tests.
"""

import io
import json
import urllib.error

import pytest

from almurrib.core.errors import AuthenticationError
from almurrib.providers import catalog
from almurrib.providers.catalog import (
    RefreshResult,
    cached_models,
    fetch_litellm_models,
    fetch_models_dev_models,
    refresh_models,
    static_models,
    store_models,
)
from almurrib.providers.discovery import (
    SOURCE_LITELLM,
    SOURCE_LIVE,
    SOURCE_MODELS_DEV,
    SOURCE_STATIC,
)
from almurrib.providers.registry import get_definition


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _json_resp(body: dict):
    def fake(req, timeout=0):
        return _Resp(json.dumps(body).encode())
    return fake


def _http_error(url: str, status: int, body: dict):
    raw = json.dumps(body).encode()
    return urllib.error.HTTPError(url, status, "e", {}, io.BytesIO(raw))


def _timeout(req, timeout=0):
    raise urllib.error.URLError(TimeoutError("timed out"))


# -- 1. official live discovery success --------------------------------------

def test_official_live_success_beats_static(monkeypatch):
    """A current live list (new ids) wins; static list never consulted."""
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _json_resp({"data": [{"id": "gpt-5-new"}, {"id": "gpt-4o-mini"}]}),
    )
    result = refresh_models(get_definition("openai"), api_key="k",
                            base_url="https://api.openai.com/v1")
    assert result.source == SOURCE_LIVE
    assert [m.id for m in result.models] == ["gpt-5-new", "gpt-4o-mini"]
    assert result.error is None


# -- 2. official 401 must raise (never masked by fallback) --------------------

def test_official_401_raises_without_fallback(monkeypatch):
    def fake(req, timeout=0):
        raise _http_error(req.full_url, 401, {"error": {"message": "bad key"}})

    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(AuthenticationError):
        refresh_models(get_definition("openai"), api_key="k",
                       base_url="https://api.openai.com/v1")


# -- 3/4/5. official 429 / timeout / malformed -> external --------------------

def _litellm_ok(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _json_resp({"object": "list", "has_more": False, "data": [
            {"id": "gpt-4o-mini", "mode": "chat", "max_input_tokens": 128000,
             "supports_response_schema": True},
        ]}),
    )


def _official_fails_then(monkeypatch, failure):
    calls = []

    def fake(req, timeout=0):
        calls.append(req.full_url)
        if "/model_catalog" in req.full_url or "models.dev" in req.full_url:
            return _Resp(json.dumps(
                {"object": "list", "has_more": False, "data": [
                    {"id": "gpt-4o-mini", "mode": "chat",
                     "max_input_tokens": 128000,
                     "supports_response_schema": True},
                ]}).encode())
        raise failure(req)

    monkeypatch.setattr("urllib.request.urlopen", fake)
    return calls


def test_official_429_falls_back_to_external(monkeypatch):
    calls = _official_fails_then(
        monkeypatch,
        _http_error("https://api.openai.com/v1/models", 429,
                    {"error": {"message": "slow"}}))
    result = refresh_models(get_definition("openai"), api_key="k",
                            base_url="https://api.openai.com/v1")
    assert result.source == SOURCE_LITELLM
    assert [m.id for m in result.models] == ["gpt-4o-mini"]
    assert result.models[0].json_support is True
    assert result.models[0].context_length == 128000
    assert result.error is not None  # official failure kept visible
    assert any("model_catalog" in url for url in calls)


def test_official_timeout_falls_back_to_external(monkeypatch):
    _official_fails_then(monkeypatch, _timeout)
    result = refresh_models(get_definition("openai"), api_key="k",
                            base_url="https://api.openai.com/v1")
    assert result.source == SOURCE_LITELLM
    assert result.error is not None


def test_official_malformed_falls_back_to_external(monkeypatch):
    def fake(req, timeout=0):
        if "model_catalog" in req.full_url:
            return _Resp(json.dumps(
                {"object": "list", "has_more": False, "data": []}).encode())
        return _Resp(b"not json{")

    monkeypatch.setattr("urllib.request.urlopen", fake)
    result = refresh_models(get_definition("openai"), api_key="k",
                            base_url="https://api.openai.com/v1")
    assert result.source in (SOURCE_LITELLM, SOURCE_STATIC)


# -- 6. Models.dev fallback ----------------------------------------------------

MODELS_DEV_EXCERPT = {
    "cohere": {
        "id": "cohere", "name": "Cohere",
        "models": {
            "command-a-translate-08-2025": {
                "id": "command-a-translate-08-2025",
                "name": "Command A Translate",
                "modalities": {"input": ["text"], "output": ["text"]},
                "reasoning": False, "tool_call": False,
                "structured_output": False,
                "limit": {"context": 8000, "output": 8000},
                "cost": {"input": 1.0, "output": 2.0},
            }
        },
    }
}


def test_models_dev_fallback_parse(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", _json_resp(MODELS_DEV_EXCERPT))
    models = fetch_models_dev_models("cohere", provider_id="cohere")
    assert [m.id for m in models] == ["command-a-translate-08-2025"]
    (model,) = models
    assert model.source == SOURCE_MODELS_DEV
    assert model.input_modalities == ("text",)
    assert model.context_length == 8000
    assert model.json_support is False
    assert model.pricing["input"] == 1.0


def test_models_dev_missing_section_raises(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _json_resp({"nope": {}}))
    from almurrib.core.errors import InvalidResponseError

    with pytest.raises(InvalidResponseError):
        fetch_models_dev_models("cohere", provider_id="cohere")


# -- 7. LiteLLM fallback -------------------------------------------------------

def test_litellm_parse_unprefix_chat_filter_status(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _json_resp({"object": "list", "has_more": False, "data": [
            {"id": "openrouter/anthropic/claude-x", "mode": "chat",
             "max_input_tokens": 200000, "supports_response_schema": True,
             "supports_reasoning": False, "supports_function_calling": True},
            {"id": "openrouter/midjourney", "mode": "image_generation"},
            {"id": "old-model", "mode": "chat", "deprecation_date": "2026-01-01"},
        ]}),
    )
    models = fetch_litellm_models("openrouter", provider_id="openrouter")
    # Exact ids preserved minus the catalog's own "<filter>/" prefix.
    assert [m.id for m in models] == ["anthropic/claude-x", "old-model"]
    assert all(m.source == SOURCE_LITELLM for m in models)
    assert models[0].context_length == 200000
    assert models[0].json_support is True
    assert models[0].reasoning is False
    assert models[0].tools is True
    assert models[1].status == "deprecated"


def test_litellm_unknown_fields_stay_unknown(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _json_resp({"object": "list", "has_more": False,
                    "data": [{"id": "m", "mode": "chat"}]}),
    )
    (model,) = fetch_litellm_models("openai", provider_id="openai")
    assert model.context_length is None
    assert model.json_support is None
    assert model.status is None
    assert model.free is None


# -- 8. static fallback ---------------------------------------------------------

def test_static_fallback_labeled_and_last(monkeypatch):
    def down(req, timeout=0):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr("urllib.request.urlopen", down)
    result = refresh_models(get_definition("openai"), api_key="k",
                            base_url="https://api.openai.com/v1")
    assert result.source == SOURCE_STATIC
    assert {m.id for m in result.models} == set(
        get_definition("openai").fallback_models)
    assert result.error is not None


def test_static_models_helper_labels_source():
    models = static_models(get_definition("cohere"))
    assert models and all(m.source == SOURCE_STATIC for m in models)
    assert all(m.provider == "cohere" for m in models)


# -- 9. merge behavior -----------------------------------------------------------

def test_official_success_never_calls_external(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _json_resp({"data": [{"id": "live-1"}]}),
    )

    def boom(*a, **k):
        raise AssertionError("external must not be consulted")

    monkeypatch.setattr(catalog, "fetch_litellm_models", boom)
    monkeypatch.setattr(catalog, "fetch_models_dev_models", boom)
    result = refresh_models(get_definition("openai"), api_key="k",
                            base_url="https://api.openai.com/v1")
    assert result.source == SOURCE_LIVE
    assert [m.id for m in result.models] == ["live-1"]


def test_official_404_uses_external(monkeypatch):
    def fake(req, timeout=0):
        if req.full_url.endswith("/models"):
            raise _http_error(req.full_url, 404, {})
        return _Resp(json.dumps(
            {"object": "list", "has_more": False,
             "data": [{"id": "m", "mode": "chat"}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake)
    result = refresh_models(get_definition("openai"), api_key="k",
                            base_url="https://api.openai.com/v1")
    assert result.source == SOURCE_LITELLM


# -- 10. cache behavior ------------------------------------------------------------

def test_cache_roundtrip_and_ttl(tmp_path):
    import time

    from almurrib.providers.discovery import ModelInfo

    models = [ModelInfo(id="a", source=SOURCE_LIVE, retrieved_at="t")]
    catalog.store_models("openai", models, SOURCE_LIVE, "t", base_dir=tmp_path)
    got = cached_models("openai", now_epoch=time.time(), base_dir=tmp_path)
    assert got is not None
    cached, source, _ = got
    assert [m.id for m in cached] == ["a"]
    assert source == SOURCE_LIVE
    # stale entries are invisible (caller refreshes instead)
    old = cached_models("openai", now_epoch=time.time() + 10**8, base_dir=tmp_path)
    assert old is None
    assert cached_models("missing", now_epoch=time.time(), base_dir=tmp_path) is None


def test_cache_holds_no_secrets(tmp_path):
    from almurrib.providers.discovery import ModelInfo

    catalog.store_models("openai", [ModelInfo(id="a")], SOURCE_LIVE, "t",
                         base_dir=tmp_path)
    content = (tmp_path / catalog.CACHE_FILENAME).read_text(encoding="utf-8")
    assert "Bearer" not in content
    assert "sk-" not in content


# -- 12. provider switch uses per-provider catalog ids -----------------------------

def test_kimi_uses_moonshot_catalog_id(monkeypatch):
    seen = []

    def fake(req, timeout=0):
        seen.append(req.full_url)
        return _Resp(json.dumps(
            {"object": "list", "has_more": False, "data": []}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake)
    fetch_litellm_models("moonshot", provider_id="kimi")
    assert seen and "provider=moonshot" in seen[0]


def test_discovery_strategy_resolution():
    from almurrib.providers.registry import (
        LITELLM_CATALOG,
        MODELS_DEV,
        OFFICIAL_API,
        STATIC_FALLBACK,
        discovery_strategy,
    )

    assert discovery_strategy(get_definition("openai")) == [
        OFFICIAL_API, LITELLM_CATALOG, STATIC_FALLBACK]
    assert discovery_strategy(get_definition("tokenrouter")) == [
        OFFICIAL_API, MODELS_DEV, STATIC_FALLBACK]
    assert discovery_strategy(get_definition("llamacpp")) == [
        OFFICIAL_API, STATIC_FALLBACK]


def test_empty_official_list_falls_through():
    def fake(req, timeout=0):
        if req.full_url.endswith("/models"):
            return _Resp(json.dumps({"data": []}).encode())
        return _Resp(json.dumps(
            {"object": "list", "has_more": False,
             "data": [{"id": "m", "mode": "chat"}]}).encode())

    import urllib.request

    orig = urllib.request.urlopen
    urllib.request.urlopen = fake
    try:
        result = refresh_models(get_definition("openai"), api_key="k",
                                base_url="https://api.openai.com/v1")
    finally:
        urllib.request.urlopen = orig
    assert result.source == SOURCE_LITELLM
    assert [m.id for m in result.models] == ["m"]
    assert result.error is not None  # empty official kept visible


def test_catalog_http_errors_mapped(monkeypatch):
    from almurrib.core.errors import AuthenticationError, ProviderError
    from almurrib.providers import catalog as catalog_module

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(req.full_url, 401, {"error": {"message": "no"}})))
    with pytest.raises(AuthenticationError):
        catalog_module._get_json("https://x.test/cat", timeout_seconds=5)

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(req.full_url, 500, {"oops": 1})))
    with pytest.raises(ProviderError) as exc_info:
        catalog_module._get_json("https://x.test/cat", timeout_seconds=5)
    assert exc_info.value.http_status == 500


# -- RefreshResult shape -------------------------------------------------------------

def test_refresh_result_defaults():
    result = RefreshResult(models=[], source=SOURCE_STATIC)
    assert result.error is None
