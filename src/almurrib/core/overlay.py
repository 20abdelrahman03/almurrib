"""Localization-overlay architecture (Phase 2b foundation, no Phase 3).

Hard product rule: a game's base/original locale stays English wherever
possible. Arabic reaches the player as an OVERLAY — replacement content
selected at display time — not by forcing every engine to register Arabic
as an official locale.

```text
Game base locale = English
        |
Almurrib overlay (strategy per engine)
        |
Displayed localization = Arabic
        |
Player sees Arabic (settings may still read "English")
```

The temporary ``ar`` locale + language button used in the Ren'Py manual
rendering test is ONE strategy instance (``LANGUAGE_DIR``), not the product
architecture. Future engines implement their own strategy behind the
``OverlayStrategy`` protocol; nothing here injects code into games (that is
Phase 3 runtime work, explicitly out of scope).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class OverlayStrategy(str, Enum):
    """How displayed text becomes Arabic for one engine."""

    LANGUAGE_DIR = "language_dir"  # engine loads tl/<lang>/ files (Ren'Py test)
    LOOKUP_OVERRIDE = "lookup_override"  # engine string-lookup hook
    RESOURCE_PATCH = "resource_patch"  # patched asset bundles on disk
    INTERCEPTION = "interception"  # runtime text interception (Phase 3)


@dataclass(frozen=True)
class OverlayPlan:
    """One engine's answer to the overlay question."""

    engine: str  # e.g. "renpy"
    base_locale: str = "en"  # game language, left unchanged
    displayed_locale: str = "ar"  # what the player actually sees
    active: bool = False  # an overlay is staged/selected
    strategy: OverlayStrategy = OverlayStrategy.LANGUAGE_DIR
    details: dict[str, str] = field(default_factory=dict)

    @property
    def leaves_base_english(self) -> bool:
        """The product invariant: base locale untouched by the overlay."""
        return self.base_locale == "en"


@dataclass(frozen=True)
class Locales:
    """The three distinct locale concepts (never conflate them)."""

    ui_locale: str  # Almurrib's own interface language
    game_base_locale: str  # the target game's original locale
    displayed_locale: str  # what the player sees via overlay
