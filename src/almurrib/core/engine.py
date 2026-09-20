"""Engine adapter interface (dependency inversion point).

The core pipeline talks to engines *only* through this protocol. Each
engine-specific implementation lives under ``engine_adapters/`` and stays
replaceable. Today: Ren'Py extraction. Later: reinjection, then other
engines (Unity, Unreal, RPG Maker, Godot) implement the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from almurrib.core.model import EngineType, LocalizationEntry


@dataclass
class DetectionResult:
    """Outcome of asking an adapter "is this your kind of game?"."""

    engine: EngineType
    confidence: float  # 0.0 .. 1.0
    reasons: list[str] = field(default_factory=list)

    @property
    def is_match(self) -> bool:
        return self.confidence > 0.0


@runtime_checkable
class EngineAdapter(Protocol):
    """Contract every engine adapter must satisfy (extraction half)."""

    @property
    def engine_type(self) -> EngineType:
        """Which engine this adapter handles."""
        ...

    def detect(self, game_dir: Path) -> DetectionResult:
        """Inspect ``game_dir`` and report whether it looks like this engine.

        Must never raise for a merely-unrelated directory; it returns a
        result with confidence 0.0 instead.
        """
        ...

    def extract(self, game_dir: Path) -> list[LocalizationEntry]:
        """Extract translatable text and normalize it into entries.

        Entries must carry enough :class:`~almurrib.core.model.SourceRef`
        information to allow reinjection later.
        """
        ...
