"""Configuration layer.

Precedence (highest first): explicit function args > environment variables
(ALMURRIB_*) > a local ``.env``-style file > defaults.

Secrets come from the environment or a local untracked file — never from
source. ``.env.example`` documents the available knobs with placeholders.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from almurrib.core.provider import ProviderConfig

ENV_PREFIX = "ALMURRIB_"

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_PROVIDER = "openai_compat"


def _load_env_file(path: Path) -> dict[str, str]:
    """Parse a minimal KEY=VALUE .env file (no quotes expansion, no export)."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings."""

    provider: str
    base_url: str
    model: str
    api_key: str | None
    source_lang: str
    target_lang: str
    batch_size: int
    timeout_seconds: float
    max_retries: int
    database_path: Path
    output_dir: Path

    def provider_config(self) -> ProviderConfig:
        if not self.api_key:
            from almurrib.core.errors import AuthenticationError

            raise AuthenticationError(
                "no API key configured",
                hint="set ALMURRIB_API_KEY (see .env.example). Keys are BYO and never committed.",
            )
        return ProviderConfig(
            provider=self.provider,
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            timeout_seconds=self.timeout_seconds,
            batch_size=self.batch_size,
            max_retries=self.max_retries,
        )


def load_settings(
    *,
    env_file: Path | None = None,
    overrides: dict[str, str] | None = None,
    environ: dict[str, str] | None = None,
) -> Settings:
    """Resolve settings from .env file, process env, and explicit overrides."""
    environ = dict(os.environ if environ is None else environ)
    file_values = _load_env_file(env_file or Path(".env"))

    def get(key: str, default: str = "") -> str:
        env_key = ENV_PREFIX + key
        if overrides and env_key in overrides:
            return overrides[env_key]
        if env_key in environ:
            return environ[env_key]
        return file_values.get(env_key, default)

    def get_float(key: str, default: float) -> float:
        raw = get(key)
        try:
            return float(raw) if raw else default
        except ValueError:
            return default

    def get_int(key: str, default: int) -> int:
        raw = get(key)
        try:
            return int(raw) if raw else default
        except ValueError:
            return default

    return Settings(
        provider=get("PROVIDER", DEFAULT_PROVIDER),
        base_url=get("BASE_URL", DEFAULT_BASE_URL),
        model=get("MODEL", DEFAULT_MODEL),
        api_key=get("API_KEY") or None,
        source_lang=get("SOURCE_LANG", "en"),
        target_lang=get("TARGET_LANG", "arabic"),
        batch_size=get_int("BATCH_SIZE", 20),
        timeout_seconds=get_float("TIMEOUT_SECONDS", 60.0),
        max_retries=get_int("MAX_RETRIES", 3),
        database_path=Path(get("DATABASE", "almurrib.db")),
        output_dir=Path(get("OUTPUT_DIR", "out")),
    )
