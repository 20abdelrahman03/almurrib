"""Core domain: normalized localization model, pipeline, cache, errors."""

from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
    TranslationSource,
    content_hash,
)
from almurrib.core.engine import EngineAdapter, DetectionResult

__all__ = [
    "EngineType",
    "EntryStatus",
    "LocalizationEntry",
    "SourceRef",
    "TranslationSource",
    "content_hash",
    "EngineAdapter",
    "DetectionResult",
]
