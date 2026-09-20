"""Core domain: normalized localization model, pipeline, cache, errors."""

from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
    content_hash,
)
from almurrib.core.engine import EngineAdapter, DetectionResult

__all__ = [
    "EngineType",
    "EntryStatus",
    "LocalizationEntry",
    "SourceRef",
    "content_hash",
    "EngineAdapter",
    "DetectionResult",
]
