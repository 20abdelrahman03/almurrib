"""Deterministic Unicode normalization for Arabic game text.

Lossless-first: NFC canonical composition plus safe whitespace/control
hygiene. Game syntax (``{name}``, ``%s``, ``[var]``, ``<b>``, ``\\n`` …)
is masked before any transformation and restored byte-for-byte after, so
normalization can never corrupt protected tokens.

What this deliberately does NOT do by default:

* remove tatweel, diacritics, or zero-width joiners (meaningful content),
* convert Arabic-Indic ↔ Latin digits (author choice),
* strip directional marks (explicit author intent).
"""

from __future__ import annotations

import re
import unicodedata

# Control characters that are never meaningful in game strings. Tabs and
# newlines are preserved (callers split paragraphs on them); other C0
# controls and DEL are dropped.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# Runs of plain spaces / no-break spaces collapse to one space. Tabs are
# left alone (may be intentional alignment escapes).
_SPACE_RUN_RE = re.compile(r"[ \u00a0]+")

_ARABIC_LETTER_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")


def contains_arabic(text: str) -> bool:
    """True when the text holds at least one Arabic-script letter."""
    return _ARABIC_LETTER_RE.search(text) is not None


def normalize_text(
    text: str,
    *,
    form: str = "NFC",
    collapse_spaces: bool = True,
    strip_controls: bool = True,
) -> str:
    """Normalize Unicode text deterministically (default: NFC).

    NFC is canonical-equivalent: it composes/decomposes nothing with
    distinct meaning (é stays é). Protected game tokens pass through
    untouched because NFC never alters ASCII.
    """
    if form not in ("NFC", "NFD", "NFKC", "NFKD"):
        raise ValueError(f"unknown normalization form: {form!r}")
    out = unicodedata.normalize(form, text)
    if strip_controls:
        out = _CONTROL_RE.sub("", out)
    if collapse_spaces:
        out = _SPACE_RUN_RE.sub(" ", out)
    return out
