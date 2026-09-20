"""High-level localization workflow shared by CLI commands.

Keeps the CLI thin: all orchestration (extract → translate → persist →
export) lives here, is engine-agnostic, and is directly testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from almurrib.core.model import EntryStatus, LocalizationEntry
from almurrib.core.pipeline import LocalizationPipeline, PipelineContext
from almurrib.core.provider import TranslationProvider
from almurrib.core.translate import RealTranslateStage, TranslationStats
from almurrib.storage.cache import SQLiteCache
from almurrib.storage.database import Database
from almurrib.storage.repository import EntryRepository


@dataclass
class LocalizationReport:
    engine: str = ""
    extracted: int = 0
    stats: TranslationStats = field(default_factory=TranslationStats)
    exported_files: list[str] = field(default_factory=list)
    db_path: str = ""


def extract_and_store(
    pipeline: LocalizationPipeline,
    game_dir: Path,
    db: Database,
    *,
    target_lang: str = "ar",
    project_name: str | None = None,
) -> tuple[list[LocalizationEntry], int]:
    """Detect → extract → normalize → persist. Returns (entries, project_id)."""
    context = PipelineContext(game_dir=game_dir, target_lang=target_lang)
    result = pipeline.extract(game_dir, context)
    repo = EntryRepository(db)
    engine = pipeline.detect_engine(game_dir).engine_type
    project = repo.ensure_project(
        project_name or game_dir.resolve().name, str(game_dir.resolve()), engine
    )
    repo.upsert_many(project.id, result.entries)
    return result.entries, project.id


def load_translation_memory(db: Database) -> dict[str, str]:
    """Fingerprint → translation from ALL stored entries (cross-project TM).

    Only exact fingerprints (source text + speaker + context) match, so a
    translation is never reused when the surrounding context differs.
    """
    repo = EntryRepository(db)
    memory: dict[str, str] = {}
    for entry in repo.list():
        if entry.translated_text and entry.status is not EntryStatus.FLAGGED:
            memory.setdefault(entry.fingerprint, entry.translated_text)
    return memory


def translate_entries(
    entries: list[LocalizationEntry],
    db: Database,
    provider: TranslationProvider,
    *,
    source_lang: str = "en",
    target_lang: str = "ar",
    project_id: int | None = None,
    force: bool = False,
    progress=None,  # optional callable(done: int, total: int)
) -> TranslationStats:
    """Translate entries with TM + cache + provider, then persist."""
    cache = SQLiteCache(
        db, target_lang=target_lang, provider=provider.config.identity
    )
    memory = load_translation_memory(db)
    stage = RealTranslateStage(provider, cache=cache, memory=memory, force=force)
    stats = stage.run(
        entries, source_lang=source_lang, target_lang=target_lang, progress=progress
    )
    if project_id is not None:
        EntryRepository(db).upsert_many(project_id, entries)
    return stats


def export_translations(
    pipeline: LocalizationPipeline,
    game_dir: Path,
    db: Database,
    *,
    output_dir: Path,
    target_lang: str = "ar",
) -> list[Path]:
    """Generate Ren'Py translation files from stored translations."""
    engine = pipeline.detect_engine(game_dir).engine_type
    if engine.value != "renpy":
        from almurrib.core.errors import ExportError

        raise ExportError(
            f"export not implemented for engine '{engine.value}'",
            hint="only Ren'Py export is supported in Phase 1.",
        )
    from almurrib.engine_adapters.renpy.reinject import write_translation_patch

    repo = EntryRepository(db)
    entries = [e for e in repo.list() if e.translated_text]
    return write_translation_patch(entries, target_lang=target_lang, output_dir=output_dir)
