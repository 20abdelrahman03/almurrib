"""Arabic-aware word wrapping for game text.

``textwrap`` is not sufficient: protected tokens (``{name}``, ``<b>`` …)
must never break mid-token, explicit newlines start new paragraphs, and
character count is only a fallback proxy for rendered width. Hence:

* tokenization keeps every protected span atomic (via ``arabic.masking``
  slot spans),
* a :class:`TextMetrics` abstraction supplies widths (default: 1 per
  character — deterministic fallback, documented limitation),
* invalid widths raise instead of silently producing garbage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from almurrib.core.placeholders import extract_placeholders


class TextMetrics(Protocol):
    """Rendered-width oracle. Implement with real font metrics when known."""

    def width_of(self, text: str) -> int: ...


@dataclass(frozen=True)
class CharMetrics:
    """Fallback: every character costs 1 unit.

    WRONG for proportional fonts, CJK, and emoji — but deterministic and
    honest. Prefer a font-backed implementation for real layout.
    """

    def width_of(self, text: str) -> int:
        return len(text)


def _word_atoms(paragraph: str) -> list[str]:
    """Split a paragraph into unbreakable atoms (words + protected spans)."""
    tokens = sorted(set(extract_placeholders(paragraph)), key=len, reverse=True)
    if not tokens:
        return paragraph.split(" ") if paragraph else []
    # Cut around protected spans, then split the gaps on spaces.
    spans: list[tuple[int, int]] = []
    for token in tokens:
        start = 0
        while True:
            index = paragraph.find(token, start)
            if index < 0:
                break
            end = index + len(token)
            if not any(index < e and end > s for s, e in spans):
                spans.append((index, end))
            start = end
    spans.sort()
    atoms: list[str] = []
    cursor = 0
    for start, end in spans:
        atoms.extend(paragraph[cursor:start].split(" "))
        atoms.append(paragraph[start:end])
        cursor = end
    atoms.extend(paragraph[cursor:].split(" "))
    return [atom for atom in atoms if atom != ""]


def wrap_arabic_text(
    text: str,
    max_width: int,
    metrics: TextMetrics | None = None,
    *,
    break_long_words: bool = True,
) -> list[str]:
    """Wrap logical text into lines of at most ``max_width`` units.

    Paragraphs (split on real newlines) wrap independently and are never
    merged. Protected tokens stay atomic; an atom longer than ``max_width``
    is hard-split when ``break_long_words`` is set, else it overflows on
    its own line. ``max_width < 1`` raises ValueError.
    """
    if not isinstance(max_width, int) or max_width < 1:
        raise ValueError(f"max_width must be a positive integer, got {max_width!r}")
    ruler = metrics or CharMetrics()
    lines: list[str] = []
    for paragraph in text.split("\n"):
        protected = set(extract_placeholders(paragraph))
        current: list[str] = []
        current_width = 0
        for atom in _word_atoms(paragraph):
            atom_width = ruler.width_of(atom)
            if atom in protected:
                # Atomic by contract: own line, overflows if wider.
                if current:
                    lines.append(" ".join(current))
                    current, current_width = [], 0
                lines.append(atom)
                continue
            if atom_width > max_width and break_long_words:
                if current:
                    lines.append(" ".join(current))
                    current, current_width = [], 0
                chunk, chunk_width = "", 0
                for char in atom:
                    char_width = ruler.width_of(char) or 1
                    if chunk and chunk_width + char_width > max_width:
                        lines.append(chunk)
                        chunk, chunk_width = "", 0
                    chunk += char
                    chunk_width += char_width
                if chunk:
                    current, current_width = [chunk], chunk_width
                continue
            if current and (
                current_width + ruler.width_of(" ") + atom_width > max_width
            ):
                lines.append(" ".join(current))
                current, current_width = [atom], atom_width
            else:
                if current:
                    current_width += ruler.width_of(" ")
                current.append(atom)
                current_width += atom_width
        lines.append(" ".join(current))
    return lines
