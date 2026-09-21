"""Cohere native provider tests (HTTP mocked — no network, no keys)."""

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
from almurrib.core.provider import ProviderConfig, TranslationRequest
from almurrib.providers.cohere import CohereProvider

API_KEY = "cohere-test-key"


def _provider() -> CohereProvider:
    return CohereProvider(
        ProviderConfig(
            provider="cohere",
            model="command-a-translate-08-2025",
            base_url="https://api.cohere.com",
            api_key=API_KEY,
            timeout_seconds=5,
            max_retries=0,
        )
    )


def _request(entry_id: str = "e1") -> TranslationRequest:
    return TranslationRequest(
        entry_id=entry_id, source_text="Hello!", source_lang="en", target_lang="ar"
    )


class _Resp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(status: int, body: dict):
    raw = json.dumps(body).encode()
    return urllib.error.HTTPError(
        "https://api.cohere.com/v1/chat", status, "e", {}, io.BytesIO(raw))


def _v2_body(mapping: dict) -> bytes:
    return json.dumps({"message": {"role": "assistant", "content": [
        {"type": "text", "text": json.dumps(mapping, ensure_ascii=False)},
    ]}}).encode()


def test_chat_request_shape_and_response_text(monkeypatch):
    captured = {}

    def fake(req, timeout=0):
        captured["url"] = req.full_url
        captured["auth"] = req.headers.get("Authorization")
        captured["payload"] = json.loads(req.data.decode())
        return _Resp(_v2_body({"e1": "مرحبًا!"}))

    monkeypatch.setattr("urllib.request.urlopen", fake)
    result = _provider().translate(_request())

    assert captured["url"] == "https://api.cohere.com/v2/chat"
    assert captured["auth"] == f"Bearer {API_KEY}"
    assert captured["payload"]["model"] == "command-a-translate-08-2025"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    messages = captured["payload"]["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert "JSON" in messages[0]["content"]
    assert result.translated_text == "مرحبًا!"
    assert result.model == "command-a-translate-08-2025"


def test_v1_fallback_for_legacy_models(monkeypatch):
    """A 400 demanding /v1/chat retries once on the legacy endpoint."""
    calls = []

    def fake(req, timeout=0):
        calls.append(req.full_url)
        if req.full_url.endswith("/v2/chat"):
            raise _http_error(400, {"message": "use '/v1/chat' instead"})
        body = json.dumps({"text": json.dumps({"e1": "مرحبًا!"})}).encode()
        return _Resp(body)

    monkeypatch.setattr("urllib.request.urlopen", fake)
    result = _provider().translate(_request())

    assert calls == ["https://api.cohere.com/v2/chat",
                     "https://api.cohere.com/v1/chat"]
    assert result.translated_text == "مرحبًا!"


def test_v2_format_refusal_retries_plain(monkeypatch):
    """A 400 refusing response_format retries once without it."""
    payloads = []

    def fake(req, timeout=0):
        payloads.append(json.loads(req.data.decode()))
        if "response_format" in payloads[-1]:
            raise _http_error(400, {"message": "response_format not supported"})
        return _Resp(_v2_body({"e1": "مرحبًا!"}))

    monkeypatch.setattr("urllib.request.urlopen", fake)
    assert _provider().translate(_request()).translated_text == "مرحبًا!"
    assert len(payloads) == 2
    assert "response_format" not in payloads[1]


def test_legacy_text_and_generations_shapes_parsed(monkeypatch):
    from almurrib.providers.cohere import CohereProvider as _C

    assert _C._read_v1_text({"text": "x"}) == "x"
    assert _C._read_v1_text({"generations": [{"text": "y"}]}) == "y"
    with pytest.raises(InvalidResponseError):
        _C._read_v1_text({})
    with pytest.raises(InvalidResponseError):
        _C._read_v2_text({"message": {"content": [{"type": "tool", "x": 1}]}})


def test_401_auth_without_key(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(401, {"message": "invalid api token"})),
    )
    with pytest.raises(AuthenticationError) as exc_info:
        _provider().translate(_request())
    assert API_KEY not in str(exc_info.value)
    assert exc_info.value.provider_message == "invalid api token"


def test_429_rate_limit(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(429, {"message": "too many requests"})),
    )
    with pytest.raises(RateLimitError):
        _provider().translate(_request())


def test_404_model_hint(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(404, {"message": "model not found"})),
    )
    with pytest.raises(ProviderError) as exc_info:
        _provider().translate(_request())
    assert "fetch models" in str(exc_info.value).lower()


def test_malformed_reply_raises(monkeypatch):
    def fake(req, timeout=0):
        return _Resp(json.dumps({"text": "not json"}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(InvalidResponseError):
        _provider().translate(_request())


def test_empty_reply_raises(monkeypatch):
    def fake(req, timeout=0):
        return _Resp(json.dumps({}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(InvalidResponseError):
        _provider().translate(_request())
