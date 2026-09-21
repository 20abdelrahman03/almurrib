"""OpenAI-compatible provider tests (HTTP mocked — no network)."""

import json

import pytest

from almurrib.core.errors import (
    AuthenticationError,
    InvalidResponseError,
    RateLimitError,
)
from almurrib.core.provider import ProviderConfig, TranslationRequest
from almurrib.providers.openai_compat import OpenAICompatibleProvider


def _provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        ProviderConfig(
            provider="openai_compat",
            model="test-model",
            base_url="http://api.test/v1",
            api_key="secret-key",
            timeout_seconds=5,
            max_retries=1,
        )
    )


def _request(entry_id: str = "e1", text: str = "Hello {name}!") -> TranslationRequest:
    return TranslationRequest(
        entry_id=entry_id,
        source_text=text,
        source_lang="en",
        target_lang="ar",
        speaker="Eileen",
        placeholders=["{name}"],
    )


def _http_response(mapping: dict) -> bytes:
    return json.dumps(
        {"choices": [{"message": {"content": json.dumps(mapping, ensure_ascii=False)}}]}
    ).encode("utf-8")


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_successful_batch_translation(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["auth"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(_http_response({"e1": "مرحبًا {name}!"}))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    result = _provider().translate(_request())

    assert result.translated_text == "مرحبًا {name}!"
    assert result.model == "test-model"
    assert captured["url"] == "http://api.test/v1/chat/completions"
    assert captured["auth"] == "Bearer secret-key"
    assert captured["payload"]["model"] == "test-model"
    # placeholder must be visible to the model in the prompt
    user_msg = captured["payload"]["messages"][1]["content"]
    assert "{name}" in user_msg and "Eileen" in user_msg


def test_auth_error_not_retried(monkeypatch):
    import urllib.error

    calls = []

    def fake_urlopen(request, timeout=0):
        calls.append(1)
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(AuthenticationError):
        _provider().translate(_request())
    assert len(calls) == 1  # no retry on auth errors


def test_rate_limit_retried_then_raises(monkeypatch):
    import urllib.error

    calls = []

    def fake_urlopen(request, timeout=0):
        calls.append(1)
        raise urllib.error.HTTPError(request.full_url, 429, "Too Many", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: None)
    with pytest.raises(RateLimitError):
        _provider().translate(_request())
    assert len(calls) == 2  # max_retries=1 → 2 attempts


def test_invalid_json_content_raises(monkeypatch):
    def fake_urlopen(request, timeout=0):
        body = json.dumps({"choices": [{"message": {"content": "not json"}}]}).encode()
        return _FakeResponse(body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(InvalidResponseError):
        _provider().translate(_request())


def test_batch_or_fallback_policy():
    """Shared policy: whole batch first, singles on malformed, else raise."""
    from almurrib.core.errors import InvalidResponseError
    from almurrib.providers.batch_json import batch_or_fallback

    def parse(reply, reqs):
        if reply == "bad":
            raise InvalidResponseError("malformed")
        return [f"ok:{r.entry_id}" for r in reqs]

    results, fallback = batch_or_fallback(lambda: "good", lambda r: "good",
                                          parse, [_request("a"), _request("b")])
    assert results == ["ok:a", "ok:b"] and fallback == 0

    results, fallback = batch_or_fallback(
        lambda: "bad", lambda r: "good", parse, [_request("a"), _request("b")])
    assert results == ["ok:a", "ok:b"] and fallback == 2

    import pytest

    with pytest.raises(InvalidResponseError):
        batch_or_fallback(lambda: "bad", lambda r: "bad", parse, [_request("a")])


def test_missing_ids_raise(monkeypatch):
    def fake_urlopen(request, timeout=0):
        return _FakeResponse(_http_response({"other": "x"}))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(InvalidResponseError):
        _provider().translate(_request("e1"))
