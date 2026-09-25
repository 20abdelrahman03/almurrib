"""Engine-dispatched export (keeps engine branches out of core workflow).

Each engine maps its stored translations to output files its own way:
Ren'Py emits a string-translation patch; RPG Maker emits translated data
files. Unknown engines raise ExportError with an honest message.
"""

from __future__ import annotations

from pathlib import Path

from almurrib.core.errors import ExportError
from almurrib.core.model import EngineType, EntryStatus, LocalizationEntry
from almurrib.storage.repository import EntryRepository


def export_for_engine(
    engine: EngineType,
    game_dir: Path,
    db: "Database",
    *,
    output_dir: Path,
    target_lang: str,
    project_id: int | None = None,
    visual_arabic: bool = False,
) -> list[Path]:
    """Generate output files for one engine from stored translations."""
    repo = EntryRepository(db)
    if engine is EngineType.RENPY:
        from almurrib.engine_adapters.renpy.reinject import write_translation_patch

        entries = [
            e for e in repo.list(project_id=project_id)
            if e.translated_text and e.status is not EntryStatus.OBSOLETE
        ]
        return write_translation_patch(entries, target_lang=target_lang,
                                       output_dir=output_dir)
    if engine is EngineType.RPGMAKER:
        from almurrib.engine_adapters.rpgmaker.parser import find_data_dir
        from almurrib.engine_adapters.rpgmaker.reinject import write_data_patch

        found = find_data_dir(game_dir.resolve())
        if found is None:
            raise ExportError(
                f"RPG Maker data dir not found under '{game_dir}'",
                hint="export needs the original game layout for write-back.",
            )
        entries: list[LocalizationEntry] = [
            e for e in repo.list(project_id=project_id)
            if e.translated_text and e.status is not EntryStatus.OBSOLETE
        ]
        return write_data_patch(entries, game_root=game_dir.resolve(),
                                output_dir=output_dir)
    if engine is EngineType.UNITY:
        from almurrib.engine_adapters.unity.reinject import write_asset_patch

        entries = [
            e for e in repo.list(project_id=project_id)
            if e.translated_text and e.status is not EntryStatus.OBSOLETE
        ]
        return write_asset_patch(entries, game_root=game_dir.resolve(),
                                 output_dir=output_dir,
                                 visual_arabic=visual_arabic)
    raise ExportError(
        f"export not implemented for engine '{engine.value}'",
        hint="supported in Phase 3: Ren'Py, RPG Maker MV/MZ, Unity.",
    )
