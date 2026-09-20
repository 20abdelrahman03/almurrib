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
