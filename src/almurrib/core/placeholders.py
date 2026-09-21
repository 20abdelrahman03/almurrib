"""Placeholder / protected-token detection and validation.

Game text is full of runtime tokens that must survive translation
byte-for-byte: Ren'Py substitutions ``[variable]``, Python-style
``{player_name}`` / ``{0}``, printf-style ``%s``/``%d``/``%1$s``, markup
like ``<color=red>``/``</color>``, and escaped newlines ``\\n``.

Strategy: extract the conservative token set before sending text to a
provider, then verify after translation that every token still exists
exactly. Missing/changed tokens flag the translation instead of silently
corrupting the game.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Conservative, ordered patterns. First match wins per position.
_TOKEN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\{[A-Za-z_]\w*\}"),          # {player_name}
    re.compile(r"\{\d+\}"),                    # {0}
    re.compile(r"%\d+\$[sd]"),                 # %1$s
    re.compile(r"%[sdif]"),                    # %s %d %i %f
    re.compile(r"</?[A-Za-z][^>]*>"),          # <color=red> </color> <b> ...
    re.compile(r"\[[A-Za-z_][\w.]*\]"),        # Ren'Py substitution [variable]
    re.compile(r"\\[nt]"),                     # literal \n \t escapes
]


@dataclass(frozen=True)
class PlaceholderReport:
    """Result of validating a translation against its source tokens."""

    required: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing


from functools import lru_cache


@lru_cache(maxsize=8192)
def _extract_cached(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for pattern in _TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            token = match.group(0)
            if token not in found:
                found.append(token)
    return tuple(found)


def extract_placeholders(text: str) -> list[str]:
    """Return the protected tokens found in ``text`` (order-preserving, deduped).

    Backed by a bounded cache: translation runs extract the same source
    texts repeatedly (QA rules, prompts, masking), and extraction is pure.
    A fresh list is returned every call so callers can never mutate the
    cached tuple.
    """
    return list(_extract_cached(text))


def validate_translation(source_text: str, translated_text: str) -> PlaceholderReport:
    """Verify every source token survived into the translation."""
    required = extract_placeholders(source_text)
    missing: list[str] = []
    for token in required:
        if token not in translated_text:
            missing.append(token)
    present_in_translation = set(extract_placeholders(translated_text))
    extra = [t for t in present_in_translation if t not in set(required)]
    return PlaceholderReport(required=required, missing=missing, extra=extra)
