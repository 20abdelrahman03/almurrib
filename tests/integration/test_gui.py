"""GUI tests — headless-safe.

These verify the GUI module without requiring a display:

* the module imports,
* the service helpers (config loading, provider building, log redaction)
  behave correctly,
* the GUI calls the existing workflow services (not a duplicate engine).

Tests that need a real Tk window are skipped when no display is available
(e.g. CI/headless), so the default suite stays reliable.
"""

import os

import pytest

from almurrib.core.config import ENV_PREFIX, load_settings, save_env_file


def test_gui_module_imports():
    import almurrib.gui

    assert hasattr(almurrib.gui, "AlmurribApp")
    assert hasattr(almurrib.gui, "main")


def test_save_and_load_config_roundtrip(tmp_path, monkeypatch):
    """Save Configuration writes a .env the loader reads back."""
    monkeypatch.delenv(ENV_PREFIX + "API_KEY", raising=False)
    env_path = tmp_path / ".env"
    save_env_file(env_path, {
        ENV_PREFIX + "PROVIDER": "openai_compat",
        ENV_PREFIX + "BASE_URL": "https://api.test/v1",
        ENV_PREFIX + "MODEL": "test-model",
        ENV_PREFIX + "API_KEY": "super-secret-key",
        ENV_PREFIX + "TARGET_LANG": "arabic",
    })
    settings = load_settings(env_file=env_path, environ={})
    assert settings.model == "test-model"
    assert settings.base_url == "https://api.test/v1"
    assert settings.target_lang == "arabic"
    # the key round-trips into the provider config but is never echoed
    assert settings.provider_config().api_key == "super-secret-key"


def test_gui_does_not_log_api_key(tmp_path, monkeypatch):
    """The log writer must redact the API key from any message."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from almurrib.gui.app import AlmurribApp
    from tkinter import Tk

    root = Tk()
    root.withdraw()
    try:
        app = AlmurribApp(root)
        app.set_mode("advanced")
        app.api_key.set("super-secret-key")
        app._info("failed with key super-secret-key in header")
        content = app.log.get("1.0", "end")
        assert "super-secret-key" not in content
        assert "***" in content
    finally:
        root.destroy()


def _display_available() -> bool:
    if os.name == "nt":
        return True  # Windows always has a desktop in this dev context
    return bool(os.environ.get("DISPLAY"))


def test_format_translation_error_shows_http_details():
    """Provider failure must reach the GUI log with useful details, no key."""
    pytest.importorskip("tkinter")
    from almurrib.core.translate import TranslationStats
    from almurrib.gui.app import format_translation_error

    stats = TranslationStats(
        total=75,
        failed=75,
        errors=["[translate.auth] invalid or missing API key (HTTP 401): Invalid API key"],
        first_error="[translate.auth] invalid or missing API key (HTTP 401): Invalid API key",
        first_http_status=401,
        first_provider_message="Invalid API key",
    )
    message = format_translation_error(
        provider="openai_compat",
        base_url="https://openrouter.ai/api/v1",
        model="qwen/qwen3-30b-a3b:free",
        stats=stats,
    )
    assert "Provider: openai_compat" in message
    assert "Base URL: https://openrouter.ai/api/v1" in message
    assert "Model: qwen/qwen3-30b-a3b:free" in message
    assert "HTTP Status: 401" in message
    assert "Message: Invalid API key" in message
    assert "sk-" not in message and "Bearer" not in message


def test_format_translation_error_without_structured_details():
    """Non-HTTP failures still produce a useful Cause line."""
    pytest.importorskip("tkinter")
    from almurrib.core.translate import TranslationStats
    from almurrib.gui.app import format_translation_error

    stats = TranslationStats(total=3, failed=3, first_error="boom")
    message = format_translation_error(
        provider="openai_compat", base_url="https://x", model="m", stats=stats
    )
    assert "Translation failed (3/3 failed)" in message
    assert "HTTP Status" not in message
    assert "Cause: boom" in message


def test_provider_dropdown_lists_registry(tmp_path, monkeypatch):
    """Provider selector comes from the registry (no GUI rewrite per provider)."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp
    from almurrib.providers.registry import PROVIDERS

    root = Tk()
    root.withdraw()
    try:
        app = AlmurribApp(root)
        app.set_mode("advanced")
        values = list(app.prov_combo.cget("values"))
        for definition in PROVIDERS.values():
            assert definition.display_name in values
        # selecting a provider refreshes the base URL, keeps other fields
        app.provider_name.set("Cohere")
        app._on_provider_changed()
        assert app.base_url.get() == "https://api.cohere.com"
    finally:
        root.destroy()


def test_fallback_models_shown_without_fetch(tmp_path):
    """The model dropdown is never empty, even offline with no key."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp

    root = Tk()
    root.withdraw()
    try:
        app = AlmurribApp(root)
        app.set_mode("advanced")
        app.provider_name.set("OpenRouter")
        app._on_provider_changed()
        values = list(app.model_combo.cget("values"))
        assert "qwen/qwen3-30b-a3b:free" in values
        # search narrows the fallback pool without rewriting typed text
        app.model_combo.set("qwen")
        app._filter_models()
        filtered = list(app.model_combo.cget("values"))
        assert filtered and all("qwen" in v for v in filtered)
        assert app.model_combo.get() == "qwen"
    finally:
        root.destroy()


def test_gui_receives_live_models_not_static_list(monkeypatch):
    """Regression: the OpenAI dropdown must reflect the live API response,
    not the hard-coded fallback ids."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    import json
    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp

    class _Resp:
        def __init__(self, body: bytes):
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(req, timeout=0):
        body = json.dumps({"data": [
            {"id": "gpt-5-brand-new"},
            {"id": "gpt-4o-mini"},
        ]}).encode()
        return _Resp(body)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    root = Tk()
    root.withdraw()
    try:
        app = AlmurribApp(root)
        app.set_mode("advanced")
        app.provider_name.set("OpenAI")
        app.base_url.set("https://api.openai.com/v1")
        app.api_key.set("test-key")
        result = app._refresh_models_sync()
        assert result.source == "live"
        app._apply_models(result.models, result.source)
        values = list(app.model_combo.cget("values"))
        assert "gpt-5-brand-new" in values  # live id, absent from static list
        assert "Live provider API" in app.models_source.get()
    finally:
        root.destroy()


def test_simple_mode_default_and_switch(tmp_path):
    """Simple is the default; switching preserves fields and pool."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp

    root = Tk()
    root.withdraw()
    try:
        app = AlmurribApp(root)
        assert app.ui_mode == "simple"
        assert app.btn_start.cget("text") == "START"
        assert not hasattr(app, "log")  # no internals exposed
        app.game_dir.set("some-game")
        app.provider_name.set("OpenRouter")
        app._on_provider_changed()
        app.set_mode("advanced")
        assert app.ui_mode == "advanced"
        assert hasattr(app, "log")
        assert app.game_dir.get() == "some-game"  # fields survive
        assert list(app.model_combo.cget("values"))  # pool applied
        app.set_mode("simple")
        assert app.ui_mode == "simple"
        assert app.game_dir.get() == "some-game"
    finally:
        root.destroy()


def test_ui_lang_toggle_rebuilds_without_crash(tmp_path, monkeypatch):
    """LTR/RTL switch rebuilds chrome; state (pool, fields) survives."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp

    root = Tk()
    root.withdraw()
    try:
        monkeypatch.chdir(tmp_path)  # isolated .env for UI_LANG persistence
        app = AlmurribApp(root)
        app.set_mode("advanced")
        assert app.ui_lang == "en"
        assert app.btn_detect.cget("text") == "Detect"
        app._toggle_ui_lang()
        assert app.ui_lang == "ar"
        assert app.btn_detect.cget("text") == "كشف"
        # pack side mirrored: leading widgets now pack RIGHT
        assert app.btn_translate.pack_info()["side"] == "right"
        app.model.set("custom-model")
        app._toggle_ui_lang()
        assert app.ui_lang == "en"
        assert app.btn_detect.cget("text") == "Detect"
        assert app.model.get() == "custom-model"  # typed text survives
        assert app.btn_translate.pack_info()["side"] == "left"
    finally:
        root.destroy()


def test_simple_localize_end_to_end(renpy_fixture_dir, tmp_path, monkeypatch):
    """Simple-mode START runs the whole pipeline (FakeProvider, tmp base)."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp
    from almurrib.providers.fake import FakeProvider

    root = Tk()
    root.withdraw()
    try:
        monkeypatch.chdir(tmp_path)  # managed db/out land here, not the repo
        app = AlmurribApp(root)
        assert app.ui_mode == "simple"
        app.game_dir.set(str(renpy_fixture_dir))
        monkeypatch.setattr(app, "_provider", lambda: FakeProvider())
        summary = app.run_simple_localize()
        assert "11/11 translated" in summary
        assert (tmp_path / "out" / "game" / "tl" / "arabic" / "strings.rpy").exists()
        assert (tmp_path / "almurrib.db").exists()
    finally:
        root.destroy()


def test_simple_flow_exports_only_after_success(renpy_fixture_dir, tmp_path,
                                                monkeypatch):
    """Regression: export must run on success (never stranded under raise)."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.core.errors import RateLimitError
    from almurrib.gui.app import AlmurribApp
    from almurrib.providers.fake import FakeProvider

    root = Tk()
    root.withdraw()
    try:
        monkeypatch.chdir(tmp_path)
        app = AlmurribApp(root)
        app.game_dir.set(str(renpy_fixture_dir))

        class _Down(FakeProvider):
            def translate_batch(self, requests):
                raise RateLimitError("limited", http_status=429)

        monkeypatch.setattr(app, "_provider", lambda: _Down())
        with pytest.raises(Exception):
            app.run_simple_localize()
        assert not (tmp_path / "out").exists()  # failed run exports nothing
    finally:
        root.destroy()


def test_legacy_provider_display_resolves(tmp_path):
    """Early .env files with provider=openai_compat show a real label."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp, _provider_display

    assert _provider_display("openai_compat") == "OpenAI-Compatible (custom URL)"
    root = Tk()
    root.withdraw()
    try:
        app = AlmurribApp(root)
        app.set_mode("advanced")
        assert "OpenAI-Compatible (custom URL)" in list(
            app.prov_combo.cget("values"))
    finally:
        root.destroy()


def test_apply_models_populates_selector(tmp_path):
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp
    from almurrib.providers.discovery import ModelInfo

    root = Tk()
    root.withdraw()
    try:
        app = AlmurribApp(root)
        app.set_mode("advanced")
        from almurrib.providers.discovery import SOURCE_LIVE
        app._apply_models([ModelInfo(id="a"), ModelInfo(id="b")], SOURCE_LIVE)
        assert list(app.model_combo.cget("values")) == ["a", "b"]
        assert "Live provider API" in app.models_source.get()
        # filter narrows the dropdown but never rewrites typed text
        app.model_combo.set("b")
        app._filter_models()
        assert list(app.model_combo.cget("values")) == ["b"]
        assert app.model_combo.get() == "b"
    finally:
        root.destroy()


def test_output_defaults_anchored_to_app_base(tmp_path, monkeypatch):
    """Double-clicking the EXE elsewhere must not scatter DB/output files."""
    pytest.importorskip("tkinter")
    if not _display_available():
        pytest.skip("no display available")

    from tkinter import Tk

    from almurrib.gui.app import AlmurribApp

    root = Tk()
    root.withdraw()
    try:
        monkeypatch.chdir(tmp_path)  # launch CWD differs from repo
        app = AlmurribApp(root)
        app.set_mode("advanced")
        from almurrib.core.paths import app_base_dir

        base = app_base_dir()
        assert str(app.db_path.get()).startswith(str(base))
        assert str(app.output_dir.get()).startswith(str(base))
    finally:
        root.destroy()


def test_translate_progress_callback_fires(renpy_fixture_dir, tmp_path):
    """The translate stage reports real progress the GUI can bind to."""
    from almurrib.core.pipeline import LocalizationPipeline
    from almurrib.core.workflow import extract_and_store, translate_entries
    from almurrib.engine_adapters import default_adapters
    from almurrib.providers.fake import FakeProvider
    from almurrib.storage.database import Database

    pipeline = LocalizationPipeline(adapters=default_adapters())
    ticks: list[tuple[int, int]] = []
    with Database(tmp_path / "g.db") as db:
        entries, project_id = extract_and_store(pipeline, renpy_fixture_dir, db)
        translate_entries(
            entries, db, FakeProvider(),
            source_lang="en", target_lang="arabic",
            project_id=project_id,
            progress=lambda done, total: ticks.append((done, total)),
        )
    assert ticks, "progress callback never fired"
    assert ticks[-1][0] == ticks[-1][1]  # finished at total
    assert all(d <= t for d, t in ticks)
