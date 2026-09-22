"""Error hierarchy for almurrib.

Design principle: fail clearly. Every error carries the pipeline stage in
which it happened so that a user can tell *where* things went wrong
(detection, extraction, persistence, ...), not just *that* they went wrong.
"""

from __future__ import annotations


class AlMurribError(Exception):
    """Base class for all errors raised by almurrib."""

    #: The pipeline stage the error belongs to (detection/extraction/...).
    stage: str = "core"

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        base = f"[{self.stage}] {self.message}"
        if self.hint:
            return f"{base}\n  hint: {self.hint}"
        return base


class DetectionError(AlMurribError):
    """Raised when engine detection cannot conclude."""

    stage = "detect"


class ExtractionError(AlMurribError):
    """Raised when text extraction from game resources fails."""

    stage = "extract"


class StorageError(AlMurribError):
    """Raised when persistence fails."""

    stage = "storage"


class PipelineError(AlMurribError):
    """Raised when a pipeline stage fails in an unexpected way."""

    stage = "pipeline"


class TranslationError(AlMurribError):
    """Base for translation-stage failures."""

    stage = "translate"


class ProviderError(TranslationError):
    """Generic provider/API failure.

    Carries structured details (HTTP status, provider message) so the GUI
    can show the *actual* cause instead of a bare failure count.
    """

    stage = "translate.api"

    def __init__(
        self,
        message: str,
        *,
        hint: str | None = None,
        http_status: int | None = None,
        provider_message: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint)
        self.http_status = http_status
        self.provider_message = provider_message


class AuthenticationError(ProviderError):
    """Invalid or missing API credentials."""

    stage = "translate.auth"


class RateLimitError(ProviderError):
    """Provider rate limit (HTTP 429) — retryable."""

    stage = "translate.rate_limit"


class ProviderTimeoutError(ProviderError):
    """Network/response timeout — retryable."""

    stage = "translate.timeout"


class InvalidResponseError(ProviderError):
    """The provider returned something we could not interpret."""

    stage = "translate.response"


class PlaceholderValidationError(TranslationError):
    """A translation lost or corrupted protected placeholder tokens."""

    stage = "translate.placeholders"


class TranslationAbortedError(TranslationError):
    """The run was stopped early: consecutive batches all failed.

    A run that cannot succeed must not burn thousands of entries
    (and API quota) to prove it — abort with the first cause attached.
    Untouched entries stay untranslated and retryable.
    """

    stage = "translate"


class ExportError(AlMurribError):
    """Raised when generating localization output files fails."""

    stage = "export"
