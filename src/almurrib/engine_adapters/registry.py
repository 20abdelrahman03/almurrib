"""Adapter registry.

This is the single place where the core learns which engines exist at
runtime. Adding a new engine later = implement EngineAdapter + register it
here. Nothing else in the core changes.
"""

from __future__ import annotations

from almurrib.core.engine import EngineAdapter
from almurrib.engine_adapters.renpy import RenPyAdapter


def default_adapters() -> list[EngineAdapter]:
    """All adapters shipped in this phase (currently just Ren'Py)."""
    return [RenPyAdapter()]
