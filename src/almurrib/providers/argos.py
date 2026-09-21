"""Argos Translate offline provider (optional ``offline`` extra).

True local-first translation: no key, no network, no cloud. Each request's
source text is translated directly (no batch-JSON prompt — NMT models emit
plain text, not structured JSON), results map back by entry id.

Honest limitations (documented, not hidden):

* NMT models often drop or reorder placeholders (``{name}`` may vanish).
  The pipeline's placeholder QA flags those rows FLAGGED instead of
  corrupting the game — offline output needs human review more often.
* Quality is below flagship cloud models (verified: decent MSA, see tests).
* First use needs the 88MB en->ar model: ``almurrib local-models install``.
  Nothing downloads silently; the provider errors clearly when absent.

The heavy stack (torch/ctranslate2) stays in the optional extra — default
installs and the EXE never carry it.
"""

from __future__ import annotations

from almurrib.core.errors import InvalidResponseError, ProviderError, ProviderTimeoutError
from almurrib.core.provider import (
    ProviderCapabilities,
    ProviderConfig,
    TranslationRequest,
    TranslationResult,
)
from almurrib.providers.discovery import ModelInfo


def _require_argos():
    try:
        import argostranslate.translate as _translate
    except ImportError as exc:
        raise ProviderError(
            "Argos Translate is not installed",
            hint='install it with: uv pip install "almurrib[offline]"',
        ) from exc
    return _translate


def installed_models() -> list[ModelInfo]:
    """Language pairs installed locally (for model discovery)."""
    _require_argos()

    from almurrib.providers.discovery import (
        SOURCE_STATIC,
        utcnow_iso,
    )

    models = []
    try:
        import argostranslate.package as package

        for pkg in package.get_installed_packages():
            from_code = getattr(pkg, "from_code", "?")
            to_code = getattr(pkg, "to_code", "?")
            models.append(ModelInfo(
                id=f"{from_code}_{to_code}",
                display_name=f"Argos {from_code} → {to_code} (offline)",
                json_support=False,
                source=SOURCE_STATIC,
                retrieved_at=utcnow_iso(),
                extra={"backend": "argos"},
            ))
    except Exception as exc:
        raise ProviderError(f"cannot list Argos models: {exc}") from exc
    models.sort(key=lambda m: m.id)
    return models


class ArgosProvider:
    """Offline NMT provider (one model pair per config, e.g. ``en_ar``)."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self.last_fallback_calls: int = 0
        self._translator = None

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_batch=True,  # looped internally, one text at a time
            supports_context=True,  # accepted, NMT mostly ignores it
            max_batch_size=self._config.batch_size,
            supports_json_object=False,
            supports_model_list=True,
            supports_chat=False,
        )

    # -- public API -------------------------------------------------------

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return self.translate_batch([request])[0]

    def translate_batch(self, requests: list[TranslationRequest]) -> list[TranslationResult]:
        self.last_fallback_calls = 0
        translator = self._get_translator()
        results: list[TranslationResult] = []
        for request in requests:
            try:
                text = translator.translate(request.source_text)
            except TimeoutError as exc:
                raise ProviderTimeoutError(f"Argos translation timed out: {exc}") from exc
            except Exception:
                # One bad item must not fail its siblings: skip it so the
                # stage counts it individually as failed/missing.
                continue
            if not isinstance(text, str) or not text.strip():
                continue
            results.append(TranslationResult(
                entry_id=request.entry_id,
                translated_text=text,
                provider=self._config.provider,
                model=self._config.model,
            ))
        return results

    # -- internals --------------------------------------------------------

    def _get_translator(self):
        if self._translator is not None:
            return self._translator
        translate = _require_argos()
        model = (self._config.model or "").strip() or "en_ar"
        try:
            from_code, _, to_code = model.replace("-", "_").partition("_")
            if not to_code:
                raise ValueError(f"model id must look like 'en_ar', got {model!r}")
            installed = translate.get_installed_languages()
            source = next((lang for lang in installed if lang.code == from_code), None)
            target = next((lang for lang in installed if lang.code == to_code), None)
            if source is None or target is None:
                raise LookupError(f"Argos pair '{model}' is not installed")
            self._translator = source.get_translation(target)
        except Exception as exc:
            raise ProviderError(
                f"cannot use Argos model '{model}': {exc}",
                hint="install it with: almurrib local-models install --pair en_ar",
            ) from exc
        return self._translator
