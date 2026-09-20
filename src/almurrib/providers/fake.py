"""Deterministic fake provider for offline tests and demos.

Never touches the network. Produces stable, verifiable output while
preserving placeholders — making round-trip tests fully reproducible.
"""

from __future__ import annotations

from almurrib.core.placeholders import extract_placeholders
from almurrib.core.provider import (
    ProviderCapabilities,
    ProviderConfig,
    TranslationRequest,
    TranslationResult,
)


class FakeProvider:
    """Test provider: wraps text as '<ar>text</ar>' keeping placeholders."""

    def __init__(self, config: ProviderConfig | None = None) -> None:
        self._config = config or ProviderConfig(
            provider="fake",
            model="deterministic-0",
            base_url="http://localhost.invalid",
            api_key="test-key",
        )
        self.calls: list[list[str]] = []  # record of entry-id batches

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_batch=True, supports_context=True)

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return self.translate_batch([request])[0]

    def translate_batch(self, requests: list[TranslationRequest]) -> list[TranslationResult]:
        self.calls.append([r.entry_id for r in requests])
        results: list[TranslationResult] = []
        for req in requests:
            text = self._translate_text(req)
            results.append(
                TranslationResult(
                    entry_id=req.entry_id,
                    translated_text=text,
                    provider=self._config.provider,
                    model=self._config.model,
                )
            )
        return results

    @staticmethod
    def _translate_text(req: TranslationRequest) -> str:
        # Keep placeholders in place; wrap the rest so tests can assert on it.
        text = req.source_text
        for token in extract_placeholders(text):
            text = text.replace(token, f"\x00{token}\x01")  # mark
        translated = f"<{req.target_lang}>{text}</{req.target_lang}>"
        return translated.replace("\x00", "").replace("\x01", "")
