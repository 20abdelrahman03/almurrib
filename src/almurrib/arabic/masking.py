"""Protected-span masking for Arabic processing passes.

Reshaping and BiDi must never alter, split, or reorder game tokens
(``{name}``, ``%s``, ``[var]``, ``<b>`` …). Each protected occurrence is
replaced by a distinct Private Use Area character (U+E000 upward):

* PUA characters have BiDi class L, so a masked token behaves exactly like
  the Latin/ASCII run it stands in for — the algorithm cannot interleave
  token internals with Arabic, and distinct codepoints restore by CHARACTER
  (never by position), so visual reordering cannot misassign tokens;
* the reshaper passes PUA codepoints through untouched;
* python-bidi passes them through untouched (verified: unlike LRI/PDI
  isolates, which its UBA implementation rejects outright).

If a source text already uses the sentinel range (practically never), or
slots run out, masking raises ValueError and the caller falls back to the
unprocessed text instead of corrupting it.
"""

from __future__ import annotations

from almurrib.core.placeholders import extract_placeholders

_SENTINEL_BASE = 0xE000
_SENTINEL_END = 0xF8FF  # 6400 slots per string; game lines never approach it


def _spans(text: str, token: str) -> list[tuple[int, int]]:
    """All non-overlapping occurrence spans of a literal token."""
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        index = text.find(token, start)
        if index < 0:
            return spans
        spans.append((index, index + len(token)))
        start = index + len(token)


def _sentinel(index: int) -> str:
    code = _SENTINEL_BASE + index
    if code > _SENTINEL_END:
        raise ValueError("too many protected spans in one string")
    return chr(code)


def mask_protected(text: str) -> tuple[str, dict[str, str]]:
    """Replace protected tokens with distinct PUA sentinels.

    Returns (masked_text, table) mapping each sentinel char back to its
    original token. Longer tokens are masked first so nested-looking text
    cannot partially match. Raises ValueError on sentinel-range collision.
    """
    for index in range(_SENTINEL_END - _SENTINEL_BASE + 1):
        if chr(_SENTINEL_BASE + index) in text:
            raise ValueError("source text collides with sentinel range")
    tokens = sorted(set(extract_placeholders(text)), key=len, reverse=True)
    if not tokens:
        return text, {}
    covered: list[tuple[int, int, str]] = []
    claimed: list[tuple[int, int]] = []
    for token in tokens:
        for start, end in _spans(text, token):
            if any(start < c_end and end > c_start for c_start, c_end in claimed):
                continue
            claimed.append((start, end))
            covered.append((start, end, token))
    covered.sort()
    parts: list[str] = []
    table: dict[str, str] = {}
    cursor = 0
    for start, end, token in covered:
        parts.append(text[cursor:start])
        sentinel = _sentinel(len(table))
        parts.append(sentinel)
        table[sentinel] = token
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts), table


def unmask_protected(masked: str, table: dict[str, str]) -> str:
    """Restore originals by sentinel character. Raises on any anomaly."""
    if not table:
        if any(_SENTINEL_BASE <= ord(c) <= _SENTINEL_END for c in masked):
            raise ValueError("unexpected sentinel characters in text")
        return masked
    out: list[str] = []
    for char in masked:
        if _SENTINEL_BASE <= ord(char) <= _SENTINEL_END:
            if char not in table:
                raise ValueError("unknown sentinel survived processing")
            out.append(table[char])
        else:
            out.append(char)
    return "".join(out)
