"""Model discovery tests (HTTP mocked — no network, no keys)."""

import io
import json
import urllib.error

import pytest

from almurrib.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    ProviderError,
    RateLimitError,
)
from almurrib.providers.discovery import ModelInfo, fetch_models

API_KEY = "sk-test-discovery-key"


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _ok(body: dict):
    def fake(req, timeout=0):
        assert req.get_header("Authorization") == f"Bearer {API_KEY}"
        assert req.full_url.endswith("/models") or "/models?" in req.full_url
        return _Resp(json.dumps(body).encode())
    return fake


def _http_error(status: int, body: dict):
    raw = json.dumps(body).encode()
    return urllib.error.HTTPError("https://x.test/v1/models", status, "e", {}, io.BytesIO(raw))


def test_openai_style_listing_parsed(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _ok({"data": [
            {"id": "gpt-4o-mini", "owned_by": "openai"},
            {"id": "x", "owned_by": "y", "context_length": 128000},
        ]}),
    )
    models = fetch_models(base_url="https://x.test/v1", api_key=API_KEY)
    assert [m.id for m in models] == ["gpt-4o-mini", "x"]
    assert models[1].context_length == 128000
    assert models[1].owner == "y"


def test_openrouter_extras_parsed(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _ok({"data": [{
            "id": "qwen/qwen3-30b-a3b:free",
            "context_length": 131072,
            "supported_parameters": ["temperature", "response_format"],
            "pricing": {"prompt": "0", "completion": "0"},
        }]}),
    )
    (model,) = fetch_models(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
    assert model.json_support is True
    assert model.free is True
    assert "free" in model.short_label() and "JSON" in model.short_label()


def test_cohere_listing_parsed(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _ok({"models": [
            {"name": "command-a-translate-08-2025", "endpoints": ["chat"],
             "context_length": 8000, "features": ["text-generation"]},
            {"name": "command-a-03-2025", "endpoints": ["chat"],
             "context_length": 256000, "features": ["json_mode"]},
        ]}),
    )
    models = fetch_models(
        base_url="https://api.cohere.com", api_key=API_KEY,
        models_path="/v1/models?endpoint=chat&page_size=200", discovery="cohere",
    )
    assert [m.id for m in models] == [
        "command-a-translate-08-2025", "command-a-03-2025"]
    assert models[0].context_length == 8000
    assert models[1].json_support is True


def test_unknown_metadata_stays_unknown():
    model = ModelInfo(id="mystery")
    assert model.context_length is None
    assert model.free is None
    assert model.json_support is None
    assert model.short_label() == "mystery"


def test_401_maps_to_auth_without_key(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(401, {"error": {"message": "Invalid API key"}})),
    )
    with pytest.raises(AuthenticationError) as exc_info:
        fetch_models(base_url="https://x.test/v1", api_key=API_KEY)
    assert API_KEY not in str(exc_info.value)
    assert exc_info.value.http_status == 401


def test_404_suggests_manual_entry(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(_http_error(404, {})),
    )
    with pytest.raises(ProviderError) as exc_info:
        fetch_models(base_url="https://x.test/v1", api_key=API_KEY)
    assert "manually" in str(exc_info.value)


def test_429_maps_to_rate_limit(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(429, {"error": {"message": "slow down"}})),
    )
    with pytest.raises(RateLimitError):
        fetch_models(base_url="https://x.test/v1", api_key=API_KEY)


def test_malformed_listing_raises(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", _ok({"nope": []}),
    )
    with pytest.raises(InvalidResponseError):
        fetch_models(base_url="https://x.test/v1", api_key=API_KEY)
