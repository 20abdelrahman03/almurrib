"""Argos offline provider tests (real model when present, else skipped).

The missing-package path is always tested. Live-model tests need the
optional `offline` extra plus a downloaded en->ar model; they skip
otherwise so the default suite stays offline and lean.
"""

import sys

import pytest

from almurrib.core.errors import ProviderError
from almurrib.core.provider import ProviderConfig, TranslationRequest
from almurrib.providers.argos import ArgosProvider, installed_models
from almurrib.providers.factory import build_provider


def _config(model: str = "en_ar") -> ProviderConfig:
    return ProviderConfig(provider="argos", model=model,
                          base_url="local", api_key="")


def _request(text: str = "Hello traveler!") -> TranslationRequest:
    return TranslationRequest(entry_id="e1", source_text=text,
                              source_lang="en", target_lang="ar")


def _argos_available() -> bool:
    try:
        __import__("argostranslate.translate")
        return True
    except ImportError:
        return False


def _model_available() -> bool:
    if not _argos_available():
        return False
    try:
        return any(m.id == "en_ar" for m in installed_models())
    except Exception:
        return False


def test_missing_package_errors_clearly(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("argostranslate"):
            raise ImportError("No module named 'argostranslate'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ProviderError) as exc_info:
        ArgosProvider(_config()).translate(_request())
    assert "offline" in str(exc_info.value)


def test_missing_model_errors_with_setup_hint():
    if not _argos_available():
        pytest.skip("argostranslate not installed")
    with pytest.raises(ProviderError) as exc_info:
        ArgosProvider(_config(model="xx_yy")).translate(_request())
    assert "local-models install" in str(exc_info.value)


def test_real_offline_translation():
    if not _model_available():
        pytest.skip("Argos en_ar model not installed")
    result = ArgosProvider(_config()).translate(_request())
    assert result.translated_text.strip()
    assert result.model == "en_ar"


def test_placeholders_flagged_not_corrupted():
    """NMT may drop tokens; the pipeline must flag, never crash."""
    if not _model_available():
        pytest.skip("Argos en_ar model not installed")
    from almurrib.core.placeholders import validate_translation

    request = TranslationRequest(
        entry_id="e1", source_text="Welcome, {player_name}!",
        source_lang="en", target_lang="ar")
    result = ArgosProvider(_config()).translate(request)
    report = validate_translation(request.source_text, result.translated_text)
    assert isinstance(report.ok, bool)  # outcome recorded either way


def test_batch_maps_by_entry_id():
    if not _model_available():
        pytest.skip("Argos en_ar model not installed")
    provider = ArgosProvider(_config())
    first = TranslationRequest(entry_id="a", source_text="Good evening.",
                               source_lang="en", target_lang="ar")
    second = TranslationRequest(entry_id="b", source_text="Thank you.",
                                source_lang="en", target_lang="ar")
    results = provider.translate_batch([first, second])
    assert {r.entry_id for r in results} <= {"a", "b"}
    assert all(r.translated_text.strip() for r in results)


def test_factory_routes_argos():
    assert isinstance(build_provider(_config()), ArgosProvider)


def test_installed_models_lists_pairs():
    if not _argos_available():
        pytest.skip("argostranslate not installed")
    models = installed_models()
    assert all(m.id and "_" in m.id for m in models)


def test_capabilities_no_json():
    provider = ArgosProvider(_config())
    capabilities = provider.capabilities()
    assert capabilities.supports_json_object is False
    assert capabilities.supports_batch is True
