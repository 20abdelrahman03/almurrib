"""Configuration layer tests."""

import pytest

from almurrib.core.config import load_settings
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
