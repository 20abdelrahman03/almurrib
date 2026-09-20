"""Translation provider abstraction (provider-agnostic by design).

The Core knows only this interface. Whether translation is performed by an
OpenAI-compatible API, Gemini, Kimi, OpenRouter, or a future local model is
an implementation detail of concrete providers under ``providers/``.

Provider identity (``name`` + ``model``) is part of the cache key, so
results from different providers/models never collide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from almurrib.core.model import LocalizationEntry


@dataclass(frozen=True)
class ProviderConfig:
    """Everything needed to talk to a provider. Never logged in full."""

    provider: str  # short id, e.g. "openai_compat"
    model: str  # e.g. "gemini-2.0-flash", "qwen-2.5-72b-instruct"
    base_url: str  # e.g. "https://api.openai.com/v1"
    api_key: str  # BYO key — NEVER printed or committed
    timeout_seconds: float = 60.0
    batch_size: int = 20
    max_retries: int = 3

    @property
    def identity(self) -> str:
        """Deterministic provider identity used in cache keys."""
        return f"{self.provider}:{self.model}"


@dataclass(frozen=True)
class ProviderCapabilities:
    supports_batch: bool = False
    supports_context: bool = True
    max_batch_size: int = 20


@dataclass
class TranslationRequest:
    """One unit of translation work, with context for quality."""

    entry_id: str
    source_text: str
    source_lang: str
    target_lang: str
    speaker: str | None = None
    context: str | None = None
    placeholders: list[str] = field(default_factory=list)


@dataclass
class TranslationResult:
    """Outcome of translating one entry."""

    entry_id: str
    translated_text: str
    provider: str
    model: str
    placeholders_ok: bool = True
    missing_placeholders: list[str] = field(default_factory=list)


@runtime_checkable
class TranslationProvider(Protocol):
    """The contract every translation provider must satisfy."""

    @property
    def config(self) -> ProviderConfig: ...

    def capabilities(self) -> ProviderCapabilities: ...

    def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translate a single entry."""
        ...

    def translate_batch(self, requests: list[TranslationRequest]) -> list[TranslationResult]:
        """Translate many entries. Default implementations may loop."""
        ...
