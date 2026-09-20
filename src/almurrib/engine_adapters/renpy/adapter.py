"""Ren'Py engine adapter: detection + extraction + normalization.

The adapter is deliberately self-contained: it depends on the core model
and its own parser, and the core never depends on it. Reinjection (writing
translations back into .rpy / generated translation files) belongs to the
second half of Phase 1 and will live next to this class.
"""

from __future__ import annotations

from pathlib import Path

from almurrib.core.engine import DetectionResult
from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
)
from almurrib.engine_adapters.renpy.parser import RawStatement, parse_rpy


class RenPyAdapter:
    """Extraction-first adapter for Ren'Py games."""

    @property
    def engine_type(self) -> EngineType:
        return EngineType.RENPY

    # ----- detection ----------------------------------------------------

    def detect(self, game_dir: Path) -> DetectionResult:
        reasons: list[str] = []
        confidence = 0.0
        if not game_dir.is_dir():
            return DetectionResult(self.engine_type, 0.0, ["not a directory"])

        game_subdir = game_dir / "game"
        if game_subdir.is_dir():
            confidence += 0.4
            reasons.append("contains 'game/' directory")
        rpy_files = self._find_scripts(game_dir)
        if rpy_files:
            confidence += 0.5
            reasons.append(f"found {len(rpy_files)} .rpy script(s)")
        if (game_dir / "renpy").is_dir():
            confidence += 0.1
            reasons.append("contains 'renpy/' engine directory")
        return DetectionResult(self.engine_type, min(confidence, 1.0), reasons)

    # ----- extraction ---------------------------------------------------

    def extract(self, game_dir: Path) -> list[LocalizationEntry]:
        root = game_dir.resolve()
        entries: list[LocalizationEntry] = []
        for script in self._find_scripts(root):
            for raw in parse_rpy(script, game_root=root):
                entries.append(self._normalize(raw))
        return entries

    # ----- helpers ------------------------------------------------------

    @staticmethod
    def _find_scripts(game_dir: Path) -> list[Path]:
        """All .rpy files under the game root, deterministically ordered.

        The ``renpy/`` engine directory itself is excluded (it is engine
        code, not game content).
        """
        scripts = [
            p
            for p in game_dir.rglob("*.rpy")
            if p.is_file() and "renpy" not in p.relative_to(game_dir).parts[:-1]
        ]
        return sorted(scripts, key=lambda p: p.as_posix())

    @staticmethod
    def _normalize(raw: RawStatement) -> LocalizationEntry:
        statement_kind = {
            "say": "say",
            "menu_choice": "menu",
            "translated_string": "translate_strings",
        }.get(raw.kind, raw.kind)

        ref = SourceRef(
            file=raw.file,
            line=raw.line,
            statement=statement_kind,
            extra=dict(raw.extra),
        )
        tags = {
            "say": ["dialogue"],
            "menu_choice": ["menu", "choice"],
            "translated_string": ["existing_translation"],
        }.get(raw.kind, [])

        context_parts = []
        if raw.speaker:
            context_parts.append(f"speaker:{raw.speaker}")
        context_parts.append(f"file:{raw.file}")
        context = "; ".join(context_parts)

        translated = raw.translation  # only translate-strings pairs carry one
        status = EntryStatus.TRANSLATED if translated else EntryStatus.UNTRANSLATED

        return LocalizationEntry(
            id=LocalizationEntry.make_id(EngineType.RENPY, raw.text, ref),
            engine=EngineType.RENPY,
            source_text=raw.text,
            translated_text=translated,
            speaker=raw.speaker,
            context=context,
            status=status,
            source_refs=[ref],
            tags=tags,
            metadata={
                "statement_kind": statement_kind,
                **({"speaker_var": raw.speaker_var} if raw.speaker_var else {}),
            },
        )
