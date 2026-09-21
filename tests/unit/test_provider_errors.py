"""Provider error-handling regression tests (offline, mocked HTTP)."""

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
from almurrib.providers.openai_compat import (
    OpenAICompatibleProvider,
    _extract_error_message,
)

API_KEY = "sk-test-secret-key"


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        ProviderConfig(
            provider="openai_compat",
            model="qwen/qwen3-30b-a3b:free",
            base_url="https://openrouter.ai/api/v1",
            api_key=API_KEY,
            timeout_seconds=5,
            max_retries=0,  # no retry: assert on the immediate error
        )
    )


def _request() -> TranslationRequest:
    return TranslationRequest(
        entry_id="e1", source_text="Hello!", source_lang="en", target_lang="ar"
    )


def _http_error(status: int, body: dict) -> urllib.error.HTTPError:
    raw = json.dumps(body).encode("utf-8")
    return urllib.error.HTTPError(
        "https://openrouter.ai/api/v1/chat/completions",
        status, "err", {}, io.BytesIO(raw),
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


def test_error_message_extracted_from_openai_error_body():
    raw = '{"error": {"message": "Invalid API key", "code": 401}}'
    assert _extract_error_message(raw) == "Invalid API key"
    assert _extract_error_message("not json") is None
    assert _extract_error_message("{}") is None


def test_401_raises_auth_with_provider_message_no_key(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(401, {"error": {"message": "Invalid API key", "code": 401}})
        ),
    )
    with pytest.raises(AuthenticationError) as exc_info:
        _provider().translate(_request())
    err = exc_info.value
    assert err.http_status == 401
    assert err.provider_message == "Invalid API key"
    assert "Invalid API key" in str(err)
    assert API_KEY not in str(err)          # never leak the key
    assert "Bearer" not in str(err)


def test_429_raises_rate_limit_with_message(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(429, {"error": {"message": "Rate limit exceeded"}})
        ),
    )
    with pytest.raises(RateLimitError) as exc_info:
        _provider().translate(_request())
    assert exc_info.value.http_status == 429
    assert "Rate limit exceeded" in str(exc_info.value)


def test_404_model_not_found(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(404, {"error": {"message": "Model not found"}})
        ),
    )
    with pytest.raises(ProviderError) as exc_info:
        _provider().translate(_request())
    assert exc_info.value.http_status == 404
    assert "Model not found" in str(exc_info.value)


def test_successful_openai_response_parsed(monkeypatch):
    def ok(req, timeout=0):
        assert req.full_url == "https://openrouter.ai/api/v1/chat/completions"
        assert req.headers["Authorization"] == f"Bearer {API_KEY}"
        assert req.headers["Content-type"] == "application/json"
        body = json.dumps(
            {"choices": [{"message": {"content": json.dumps({"e1": "مرحبًا!"})}}]}
        ).encode("utf-8")
        return _Resp(body)

    monkeypatch.setattr("urllib.request.urlopen", ok)
    result = _provider().translate(_request())
    assert result.translated_text == "مرحبًا!"
    assert result.model == "qwen/qwen3-30b-a3b:free"


def test_malformed_response_raises_invalid_response(monkeypatch):
    body = json.dumps({"choices": [{"message": {"content": "not json"}}]}).encode()
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp(body))
    with pytest.raises(InvalidResponseError):
        _provider().translate(_request())


def test_authorization_header_never_in_error(monkeypatch):
    """Even on a raw 500 with an echo-y body, the key must not appear."""
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: (_ for _ in ()).throw(
            _http_error(500, {"error": {"message": "internal"}})
        ),
    )
    with pytest.raises(ProviderError) as exc_info:
        _provider().translate(_request())
    assert API_KEY not in str(exc_info.value)
