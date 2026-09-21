"""Arabic layer: normalization, reshaping, BiDi, wrapping, fonts, QA.

Engine-independent, GUI-independent, provider-independent. The database
always stores canonical LOGICAL text; visual (shaped/reordered) text is
derived on demand for legacy renderers and never persisted.
"""

from almurrib.arabic.bidi import bidi_visual, to_visual, visual_paragraphs
from almurrib.arabic.fonts import FontAsset, FontMetrics, FontRegistry
from almurrib.arabic.masking import mask_protected, unmask_protected
from almurrib.arabic.normalize import contains_arabic, normalize_text
from almurrib.arabic.qa import (
    QAFlag,
    QAResult,
    arabic_qa_check,
    register_qa_rule,
)
from almurrib.arabic.reshape import is_shaped, reshape_logical
from almurrib.arabic.wrap import CharMetrics, TextMetrics, wrap_arabic_text

__all__ = [
    "CharMetrics",
    "FontAsset",
    "FontMetrics",
    "FontRegistry",
    "QAFlag",
    "QAResult",
    "TextMetrics",
    "arabic_qa_check",
    "bidi_visual",
    "contains_arabic",
    "is_shaped",
    "mask_protected",
    "normalize_text",
    "register_qa_rule",
    "reshape_logical",
    "to_visual",
    "unmask_protected",
    "visual_paragraphs",
    "wrap_arabic_text",
]
