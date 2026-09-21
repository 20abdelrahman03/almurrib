"""Shared raw-extraction record (engine-neutral shape).

Every engine parser emits these; each adapter normalizes them into
:class:`~almurrib.core.model.LocalizationEntry`. Kinds are plain strings
(``say``/``menu_choice``/``name``/``description``/...) so new engines never
force core changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawStatement:
    """One raw extracted statement before normalization."""

    kind: str
    text: str
    file: str  # path relative to game root, POSIX style
    line: int  # 1-based ordinal when known, 0 otherwise
    speaker: str | None = None  # display name when resolved, else variable
    speaker_var: str | None = None  # raw speaker/owner reference
    translation: str | None = None  # pre-existing translation, if any
    extra: dict[str, str] = field(default_factory=dict)
