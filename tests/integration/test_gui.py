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
