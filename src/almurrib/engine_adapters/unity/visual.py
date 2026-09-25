"""Visual-order Arabic for Unity legacy renderers.

Unity's legacy UI Text performs NO shaping and NO BiDi: logical Arabic
renders as disconnected LTR glyphs (verified on Hollow Knight's menu).
The fix is to feed the engine pre-shaped visual-order text — the classic
approach for shaper-less renderers.

Contract (hard):
* Input is ALWAYS canonical logical text (what the DB stores).
* Output is derived on demand at write time, never persisted.
* Applied EXACTLY once per export (``to_visual`` is not idempotent).
* Placeholders/engine tags (``<page>``, ``<br>``, ``{name}``…) travel
  through PUA masking untouched and restore by character.
* Any failure (sentinel collision, missing optional libs) falls back to
  the logical text — a plain display is never replaced by corruption.
"""

from __future__ import annotations


def visualize(text: str) -> str:
    """Logical Arabic → render-ready visual order for Unity. Total."""
    if not text:
        return text
    try:
        from almurrib.arabic import to_visual

        return to_visual(text)
    except Exception:
        return text


def needs_visual(text: str) -> bool:
    """True when shaping would change anything (Arabic script present)."""
    try:
        from almurrib.arabic import contains_arabic

        return contains_arabic(text)
    except Exception:
        return False
