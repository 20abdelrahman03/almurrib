"""Live API tests — disabled by default.

Enable explicitly with:

    ALMURRIB_RUN_LIVE_TESTS=1
    ALMURRIB_API_KEY=...        (BYO key for the configured endpoint)
    ALMURRIB_BASE_URL=...       (defaults to OpenAI)
    ALMURRIB_MODEL=...          (defaults to gpt-4o-mini)

These tests hit a real external API exactly once (a tiny request) and are
never part of the default suite. No keys are printed or logged.
"""

import os

import pytest

from almurrib.core.config import load_settings
from almurrib.core.placeholders import validate_translation
from almurrib.core.provider import TranslationRequest
from almurrib.providers import build_provider

pytestmark = pytest.mark.skipif(
    os.environ.get("ALMURRIB_RUN_LIVE_TESTS") != "1",
    reason="live API tests disabled (set ALMURRIB_RUN_LIVE_TESTS=1)",
)


def test_live_translation_preserves_placeholders():
    settings = load_settings()
    provider = build_provider(settings.provider_config())

    request = TranslationRequest(
        entry_id="live-1",
        source_text="Hello {player_name}! Welcome to the oasis.",
        source_lang=settings.source_lang,
        target_lang=settings.target_lang,
        speaker="Guide",
        context="greeting",
        placeholders=["{player_name}"],
    )
    result = provider.translate(request)

    assert result.translated_text.strip()
    report = validate_translation(request.source_text, result.translated_text)
    assert report.ok, f"placeholders lost: {report.missing}"


def test_live_model_discovery():
    """Listing models works against the configured provider (if supported)."""
    from almurrib.providers import fetch_models, get_definition

    settings = load_settings()
    definition = get_definition(settings.provider_config().provider)
    if definition is None or definition.discovery == "none":
        pytest.skip("provider has no discovery strategy")
    if not settings.api_key:
        pytest.skip("no API key configured")
    models = fetch_models(
        base_url=settings.base_url,
        api_key=settings.api_key,
        models_path=definition.models_path,
        discovery=definition.discovery,
    )
    assert models, "model catalog came back empty"
    assert all(m.id for m in models)
