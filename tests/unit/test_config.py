"""Configuration layer tests."""

import pytest

from almurrib.core.config import load_settings, save_env_file
from almurrib.core.errors import AuthenticationError


def test_defaults_without_any_config(tmp_path, monkeypatch):
    monkeypatch.delenv("ALMURRIB_API_KEY", raising=False)
    settings = load_settings(env_file=tmp_path / "missing.env", environ={})
    assert settings.provider == "openai_compat"
    assert settings.target_lang == "arabic"
    assert settings.api_key is None


def test_env_overrides_file_and_defaults(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ALMURRIB_MODEL=file-model\nALMURRIB_API_KEY=file-key\n", encoding="utf-8"
    )
    settings = load_settings(
        env_file=env_file,
        environ={"ALMURRIB_MODEL": "env-model"},
    )
    assert settings.model == "env-model"      # env beats file
    assert settings.api_key == "file-key"     # file fills the rest


def test_explicit_overrides_win(tmp_path):
    settings = load_settings(
        env_file=tmp_path / "missing.env",
        environ={"ALMURRIB_MODEL": "env-model"},
        overrides={"ALMURRIB_MODEL": "cli-model"},
    )
    assert settings.model == "cli-model"


def test_provider_config_requires_api_key(tmp_path):
    settings = load_settings(env_file=tmp_path / "missing.env", environ={})
    with pytest.raises(AuthenticationError):
        settings.provider_config()


def test_provider_config_identity(tmp_path):
    settings = load_settings(
        env_file=tmp_path / "missing.env",
        environ={"ALMURRIB_API_KEY": "k", "ALMURRIB_MODEL": "m"},
    )
    config = settings.provider_config()
    assert config.identity == "openai_compat:m"


def test_reuse_machine_tm_defaults_off_and_parses(tmp_path):
    settings = load_settings(env_file=tmp_path / "missing.env", environ={})
    assert settings.reuse_machine_tm is False
    on = load_settings(
        env_file=tmp_path / "missing.env",
        environ={"ALMURRIB_REUSE_MACHINE_TM": "1"},
    )
    assert on.reuse_machine_tm is True


def test_default_env_file_uses_cwd_in_dev(tmp_path, monkeypatch):
    import sys
    from almurrib.core.config import default_env_file

    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.chdir(tmp_path)
    assert default_env_file() == tmp_path / ".env"


def test_frozen_env_prefers_existing_cwd_config(tmp_path, monkeypatch):
    """A frozen EXE launched from a project folder finds its .env there."""
    import sys
    from almurrib.core.config import default_env_file

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.chdir(tmp_path)  # CWD has a config, exe dir does not
    (tmp_path / ".env").write_text("ALMURRIB_MODEL=cwd-model\n", encoding="utf-8")
    assert default_env_file() == tmp_path / ".env"


def test_save_env_file_merges_preserving_unknown_keys(tmp_path):
    """GUI Save must not delete keys it does not manage (batch/timeout/...)."""
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# comment\n"
        "ALMURRIB_MODEL=old-model\n"
        "ALMURRIB_BATCH_SIZE=5\n",
        encoding="utf-8",
    )
    save_env_file(env_path, {"ALMURRIB_MODEL": "new-model"})
    settings = load_settings(env_file=env_path, environ={})
    assert settings.model == "new-model"
    assert settings.batch_size == 5  # preserved, not clobbered
    content = env_path.read_text(encoding="utf-8")
    assert "# comment" in content
