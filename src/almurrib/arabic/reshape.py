"""Arabic reshaping (logical → presentation forms) for legacy renderers.

Correctness contract (read before using):

* Ren'Py, browsers, and any HarfBuzz-equipped renderer shape Arabic
  THEMSELVES. Feeding them pre-shaped text DOUBLE-shapes it. The canonical
  stored/exported translation therefore always stays LOGICAL; shaping is a
  render-time concern only, via :func:`to_visual` for renderers that need it.
* Diacritics (harakat) are PRESERVED (``delete_harakat=False``) — the
  library default would silently strip meaningful vowels.
* Protected game tokens are masked (see ``arabic.masking``) so shaping can
  never touch them.
* :func:`is_shaped` detects presentation-form text; :func:`to_visual`
  refuses to reshape twice (double processing guard).
"""

from __future__ import annotations

import re

from almurrib.arabic.masking import mask_protected, unmask_protected

# Arabic presentation forms (the output alphabet of shaping).
_SHAPED_RE = re.compile(r"[\uFE70-\uFEFF\uFB50-\uFBFF]")

_reshaper = None


def _get_reshaper():
    global _reshaper
    if _reshaper is None:
        import arabic_reshaper

        _reshaper = arabic_reshaper.ArabicReshaper(
            configuration={
                "delete_harakat": False,  # keep meaningful diacritics
                "support_ligatures": True,  # standard render-ready output
            }
        )
    return _reshaper


def is_shaped(text: str) -> bool:
    """True when the text already contains presentation-form characters."""
    return _SHAPED_RE.search(text) is not None


def reshape_logical(text: str) -> str:
    """Shape logical Arabic text (placeholder-safe, single pass).

    Raises ValueError instead of corrupting text if sentinel accounting
    breaks mid-pipeline (caller falls back to the logical text).
    """
    if not text or is_shaped(text):
        return text  # nothing to do, or already shaped: never double-shape
    masked, slots = mask_protected(text)
    shaped = _get_reshaper().reshape(masked)
    return unmask_protected(shaped, slots)
