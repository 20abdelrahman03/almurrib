"""RPG Maker MV/MZ engine adapter: detection + extraction + normalization.

Self-contained: depends on the core model and its own parser only.
Reinjection (translated data files) lives in ``reinject.py`` next to it.
"""

from __future__ import annotations

from pathlib import Path

from almurrib.core.engine import DetectionResult
from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
    TranslationSource,
)
from almurrib.engine_adapters.raw import RawStatement
from almurrib.engine_adapters.rpgmaker.parser import find_data_dir, parse_game


class RPGMakerAdapter:
    """Extraction-first adapter for RPG Maker MV/MZ JSON data."""

    @property
    def engine_type(self) -> EngineType:
        return EngineType.RPGMAKER

    # ----- detection ----------------------------------------------------

    def detect(self, game_dir: Path) -> DetectionResult:
        reasons: list[str] = []
        confidence = 0.0
        if not game_dir.is_dir():
            return DetectionResult(self.engine_type, 0.0, ["not a directory"])

        found = find_data_dir(game_dir)
        if found is None:
            return DetectionResult(self.engine_type, 0.0, ["no RPG Maker data dir"])
        data_dir, variant = found
        confidence += 0.4
        reasons.append(f"RPG Maker {variant} data dir ({data_dir.name})")
        known = [p for p in data_dir.glob("*.json")
                 if p.is_file() and p.stem in _KNOWN_STEMS]
        if known:
            confidence += min(0.5, 0.1 * len(known))
            reasons.append(f"found {len(known)} RPG Maker data file(s)")
        if (game_dir / "www" / "js" / "rpg_core.js").is_file():
            confidence += 0.05
            reasons.append("MV runtime marker (rpg_core.js)")
        if (game_dir / "js" / "rmmz_core.js").is_file():
            confidence += 0.05
            reasons.append("MZ runtime marker (rmmz_core.js)")
        return DetectionResult(self.engine_type, min(confidence, 1.0), reasons)

    # ----- extraction ---------------------------------------------------

    def extract(self, game_dir: Path) -> list[LocalizationEntry]:
        root = game_dir.resolve()
        found = find_data_dir(root)
        if found is None:
            return []
        data_dir, _ = found
        return [self._normalize(raw) for raw in parse_game(root, data_dir)]

    # ----- helpers ------------------------------------------------------

    @staticmethod
    def _normalize(raw: RawStatement) -> LocalizationEntry:
        # Shared statement vocabulary across engines (menus are "menu").
        statement_kind = {"menu_choice": "menu"}.get(raw.kind, raw.kind)
        ref = SourceRef(
            file=raw.file,
            line=raw.line,
            statement=statement_kind,
            extra=dict(raw.extra),
        )
        tags = {
            "say": ["dialogue"],
            "menu_choice": ["menu", "choice"],
            "name": ["name"],
            "description": ["description"],
            "system_terms": ["system", "terms"],
        }.get(raw.kind, [])
        context_parts = []
        if raw.speaker:
            context_parts.append(f"speaker:{raw.speaker}")
        context_parts.append(f"file:{raw.file}")
        translated = raw.translation
        return LocalizationEntry(
            id=LocalizationEntry.make_id(EngineType.RPGMAKER, raw.text, ref),
            engine=EngineType.RPGMAKER,
            source_text=raw.text,
            translated_text=translated,
            speaker=raw.speaker,
            context="; ".join(context_parts),
            status=EntryStatus.TRANSLATED if translated else EntryStatus.UNTRANSLATED,
            source_refs=[ref],
            tags=tags,
            metadata={"statement_kind": statement_kind},
            translation_source=(
                TranslationSource.IMPORTED.value if translated
                else TranslationSource.MACHINE.value
            ),
        )


_KNOWN_STEMS = frozenset({
    "System", "MapInfos", "CommonEvents", "Actors", "Classes", "Skills",
    "Items", "Weapons", "Armors", "Enemies", "States",
})
