"""The translate stage must surface the first provider error cause."""

from almurrib.core.errors import RateLimitError
from almurrib.core.model import EngineType, LocalizationEntry, SourceRef
from almurrib.core.provider import ProviderConfig
from almurrib.core.translate import RealTranslateStage
from almurrib.providers.fake import FakeProvider


def _entry() -> LocalizationEntry:
    ref = SourceRef(file="game/s.rpy", line=1)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, "Hi", ref),
        engine=EngineType.RENPY,
        source_text="Hi",
        source_refs=[ref],
    )


class _Failing(FakeProvider):
    def __init__(self):
        super().__init__(ProviderConfig(
            provider="openai_compat", model="m",
            base_url="https://x", api_key="k",
        ))

    def translate_batch(self, requests):
        raise RateLimitError(
            "rate limit exceeded (HTTP 429): Rate limit exceeded",
            http_status=429,
            provider_message="Rate limit exceeded",
        )


def test_first_error_is_surfaced():
    stage = RealTranslateStage(_Failing())
    entry = _entry()
    stats = stage.run([entry], target_lang="ar")
    assert stats.failed == 1
    assert stats.first_error is not None
    assert "429" in stats.first_error
    assert "Rate limit exceeded" in stats.first_error


def test_first_error_carries_structured_details():
    """The GUI formats HTTP status/message from these structured fields."""
    from almurrib.core.errors import AuthenticationError

    class _AuthFailing(_Failing):
        def translate_batch(self, requests):
            raise AuthenticationError(
                "invalid or missing API key (HTTP 401): Invalid API key",
                http_status=401,
                provider_message="Invalid API key",
            )

    stage = RealTranslateStage(_AuthFailing())
    stats = stage.run([_entry()], target_lang="ar")
    assert stats.failed == 1
    assert stats.first_http_status == 401
    assert stats.first_provider_message == "Invalid API key"


def test_non_provider_exception_leaves_structured_fields_empty():
    class _Boom(_Failing):
        def translate_batch(self, requests):
            raise RuntimeError("boom")

    stage = RealTranslateStage(_Boom())
    stats = stage.run([_entry()], target_lang="ar")
    assert stats.failed == 1
    assert stats.first_error is not None
    assert stats.first_http_status is None
    assert stats.first_provider_message is None
