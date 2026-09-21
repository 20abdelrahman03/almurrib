"""Shared failure reporting tests (CLI and GUI use one formatter)."""

from almurrib.core.reporting import (
    format_translation_error,
    format_translation_summary,
    provider_display_name,
    redact_secrets,
    suggest_for,
)
from almurrib.core.translate import TranslationStats


def _stats(**overrides) -> TranslationStats:
    base = dict(total=75, failed=75)
    base.update(overrides)
    return TranslationStats(**base)


def test_full_block_with_suggestion_and_retries():
    message = format_translation_error(
        provider="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen3-30b-a3b:free",
        stats=_stats(
            first_error="[translate.rate_limit] rate limit exceeded (HTTP 429)",
            first_http_status=429,
            first_provider_message="Rate limit exceeded",
        ),
        retries=3,
    )
    assert "Translation failed (75/75 failed)" in message
    assert "Provider: OpenRouter" in message
    assert "HTTP Status: 429" in message
    assert "Message: Rate limit exceeded" in message
    assert "Retries: 3" in message
    assert "Suggestion:" in message


def test_suggestions_per_cause():
    assert "API key" in (suggest_for(401) or "")
    assert "model" in (suggest_for(404) or "").lower()
    assert "batch size" in (suggest_for(429) or "")
    assert "timeout" in (suggest_for(None, "request timed out: x") or "").lower()
    assert suggest_for(None, "mystery") is None


def test_display_name_falls_back_to_identity():
    assert provider_display_name("openrouter", "openrouter:m") == "OpenRouter"
    assert provider_display_name("missing", "missing:m") == "missing:m"


def test_no_secret_echo():
    message = format_translation_error(
        provider="p", base_url="b", model="m", stats=_stats(first_error="boom")
    )
    assert "Bearer" not in message
    assert "sk-" not in message


def test_summary_counts_already_translated_as_done():
    """Regression: all-already must read 75/75, not misleading 0/75."""
    message = format_translation_summary(_stats(already_translated=75))
    assert message.startswith("75/75 translated")
    assert "already=75" in message


def test_summary_mixed_progress():
    message = format_translation_summary(
        _stats(api_translated=10, cache_hits=5, memory_hits=2,
               already_translated=50, failed=8))
    assert message.startswith("67/75 translated")
    assert "failed=8" in message


def test_redact_exact_key_and_bearer():
    text = redact_secrets("key sk-secret-123 with Bearer sk-secret-123 here",
                          ["sk-secret-123"])
    assert "sk-secret-123" not in text
    assert text.count("***") == 2


def test_redact_provider_echoed_key_fragment():
    """Providers echo masked key variants the exact match misses."""
    leaked = ("invalid or missing API key (HTTP 401): Incorrect API key "
              "provided: HlDvVOmq****************************TfgL.")
    clean = redact_secrets(leaked, ["HlDvVOmq-FULL-REAL-KEY-TfgL"])
    assert "HlDvVOmq" not in clean
    assert "Incorrect API key provided: ***" in clean


def test_redact_leaves_normal_text():
    assert redact_secrets("nothing secret here", ["k"]) == "nothing secret here"
