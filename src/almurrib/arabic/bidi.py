"""Bidirectional processing (logical ↔ visual order) for legacy renderers.

Same contract as reshaping: modern renderers (Ren'Py/HarfBuzz) perform
their own BiDi, so stored/exported text stays LOGICAL. :func:`to_visual`
exists for renderers that need explicit visual order (old engines, plain
canvas drawing, screenshots without shaping stacks).

Implementation notes:

* Paragraphs are processed independently (split on newlines) so an
  unbalanced direction in one line cannot leak into the next.
* Protected tokens travel as distinct PUA sentinels (see
  ``arabic.masking``): same-bidi-class stand-ins restored by character,
  never by position, so reordering cannot misassign them.
* ``base_dir`` default (None) keeps the Unicode first-strong heuristic
  (standard UBA behavior); pass ``"R"``/``"L"`` to force paragraph
  direction explicitly.
"""

from __future__ import annotations

from almurrib.arabic.masking import mask_protected, unmask_protected


def bidi_visual(text: str, *, base_dir: str | None = None) -> str:
    """Reorder one logical paragraph to visual order (placeholder-safe)."""
    if not text:
        return text
    from bidi.algorithm import get_display

    masked, slots = mask_protected(text)
    kwargs = {} if base_dir is None else {"base_dir": base_dir}
    visual = get_display(masked, **kwargs)
    return unmask_protected(visual, slots)


def to_visual(text: str, *, base_dir: str | None = None) -> str:
    """Full render-ready pipeline for legacy renderers: reshape then BiDi.

    NOT idempotent (verified): feeding visual output back in produces
    different output, because BiDi has no "already visual" detector. The
    architecture therefore derives visual text from canonical LOGICAL text
    on demand and never stores or re-processes it — see docs/ARABIC_LAYER.
    Newlines split paragraphs; each is processed independently.
    """
    from almurrib.arabic.reshape import reshape_logical

    return "\n".join(
        bidi_visual(reshape_logical(paragraph), base_dir=base_dir)
        for paragraph in text.split("\n")
    )


def visual_paragraphs(text: str, *, base_dir: str | None = None) -> list[str]:
    """to_visual, but returned per-paragraph (for line-based renderers)."""
    return to_visual(text, base_dir=base_dir).split("\n")
