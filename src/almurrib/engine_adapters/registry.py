"""Adapter registry.

This is the single place where the core learns which engines exist at
runtime. Adding a new engine later = implement EngineAdapter + register it
here. Nothing else in the core changes.
"""

from __future__ import annotations

from pathlib import Path

from almurrib.core.engine import EngineAdapter
from almurrib.engine_adapters.renpy import RenPyAdapter
from almurrib.engine_adapters.rpgmaker import RPGMakerAdapter
from almurrib.engine_adapters.unity import UnityAdapter


def default_adapters() -> list[EngineAdapter]:
    """All adapters shipped (Ren'Py, RPG Maker MV/MZ, Unity).

    The Unity adapter needs no UnityPy for *detection*; extraction raises
    a clear install error without the optional ``unity`` extra.
    """
    return [RenPyAdapter(), RPGMakerAdapter(), UnityAdapter()]


def misplaced_dir_hint(game_dir: Path) -> str | None:
    """Tell the user they likely picked a subfolder instead of the game root.

    Detection only recognizes game ROOTS, so pointing at ``game/``,
    ``*_Data/`` or ``data/`` fails with a generic message. This names the
    probable parent to select instead. Returns None when nothing suggests
    a misplaced pick (callers keep the original error).
    """
    game_dir = Path(game_dir)
    name = game_dir.name
    parent = game_dir.parent
    if name == "game" and (parent / "game").is_dir():
        return (f"you selected the 'game' folder itself — "
                f"select its parent instead: '{parent}'")
    if name.endswith("_Data"):
        return (f"you selected the Unity data folder itself — "
                f"select the game folder instead: '{parent}'")
    if name == "data":
        # MV layout is <root>/www/data (root is two levels up), MZ is
        # <root>/data (root is one level up).
        for root in (parent, parent.parent):
            if ((root / "www").is_dir() or (root / "js").is_dir()
                    or (root / "Game.rmmzproject").is_file()
                    or (root / "Game.rpgproject").is_file()):
                return (f"you selected the data folder itself — "
                        f"select the game folder instead: '{root}'")
    return None
