"""Ren'Py engine adapter: detection + extraction + normalization.

The adapter is deliberately self-contained: it depends on the core model
and its own parser, and the core never depends on it. Reinjection (writing
translations back into .rpy / generated translation files) belongs to the
second half of Phase 1 and will live next to this class.
"""

from __future__ import annotations

from pathlib import Path

from almurrib.core.engine import DetectionResult
from almurrib.core.errors import ExtractionError
from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
    TranslationSource,
)
from almurrib.engine_adapters.raw import RawStatement
from almurrib.engine_adapters.renpy.parser import parse_rpy


class RenPyAdapter:
    """Extraction-first adapter for Ren'Py games."""

    @property
    def engine_type(self) -> EngineType:
        return EngineType.RENPY

    def overlay_plan(self, *, target_lang: str = "ar"):
        """This adapter's overlay strategy (test-locale mechanism).

        Ren'Py discovers ``game/tl/<lang>/`` directories, so Arabic ships
        as a selectable test locale here. This is ONE strategy instance —
        other engines will answer differently (see ``core.overlay``).
        """
        from almurrib.core.overlay import OverlayPlan, OverlayStrategy

        return OverlayPlan(
            engine=self.engine_type.value,
            base_locale="en",
            displayed_locale=target_lang,
            active=False,  # activated by the player picking the language
            strategy=OverlayStrategy.LANGUAGE_DIR,
            details={"tl_dir": f"game/tl/{target_lang}/"},
        )

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
        archives = self._find_archives(game_dir)
        if archives and not rpy_files:
            # Packed game: no loose scripts, but archives hold them.
            confidence += 0.4
            reasons.append(f"found {len(archives)} .rpa archive(s)")
        if (game_dir / "renpy").is_dir():
            confidence += 0.1
            reasons.append("contains 'renpy/' engine directory")
        return DetectionResult(self.engine_type, min(confidence, 1.0), reasons)

    # ----- extraction ---------------------------------------------------

    def extract(self, game_dir: Path) -> list[LocalizationEntry]:
        import tempfile

        from almurrib.engine_adapters.renpy.rpa import detect_rpa, extract_all

        root = game_dir.resolve()
        entries: list[LocalizationEntry] = []
        for script in self._find_scripts(root):
            for raw in parse_rpy(script, game_root=root):
                entries.append(self._normalize(raw))
        for archive in self._find_archives(root):
            if detect_rpa(archive) is None:
                continue
            # Unpack scripts to a temp dir (never into the game), parse
            # them, and record archive-qualified pseudo-paths.
            with tempfile.TemporaryDirectory(prefix="almurrib-rpa-") as tmp:
                tmpdir = Path(tmp)
                try:
                    staged = extract_all(archive, tmpdir)
                except ExtractionError:
                    continue  # corrupt archive: loose scripts still count
                rel_archive = archive.relative_to(root).as_posix()
                for script in staged:
                    for raw in parse_rpy(script, game_root=tmpdir):
                        raw.file = f"{rel_archive}#{raw.file}"
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
    def _find_archives(game_dir: Path) -> list[Path]:
        """Packed ``game/*.rpa`` archives (checked for scripts at extract)."""
        game_subdir = game_dir / "game"
        if not game_subdir.is_dir():
            return []
        return sorted(game_subdir.glob("*.rpa"))

    @staticmethod
    def _normalize(raw: RawStatement) -> LocalizationEntry:
        statement_kind = {
            "say": "say",
            "menu_choice": "menu",
            "translated_string": "translate_strings",
            "character_name": "name",
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
            "character_name": ["character", "name"],
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
            # Pairs that ship with the game are pre-existing human/imported
            # work, not our machine output.
            translation_source=(
                TranslationSource.IMPORTED.value if translated
                else TranslationSource.MACHINE.value
            ),
        )
