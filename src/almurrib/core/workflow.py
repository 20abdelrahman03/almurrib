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
from almurrib.core.translate import RealTranslateStage, TMRecord, TranslationStats
from almurrib.storage.cache import SQLiteCache
from almurrib.storage.database import Database
from almurrib.storage.repository import EntryRepository, Project


@dataclass
class LocalizationReport:
    engine: str = ""
    extracted: int = 0
    stats: TranslationStats = field(default_factory=TranslationStats)
    exported_files: list[str] = field(default_factory=list)
    db_path: str = ""


def resolve_project(
    db: Database, game_dir: Path, engine_adapter=None
) -> Project | None:
    """Find the stored project for a game dir without creating one."""
    from almurrib.engine_adapters import default_adapters
    from almurrib.core.pipeline import LocalizationPipeline

    adapters = [engine_adapter] if engine_adapter is not None else default_adapters()
    engine = LocalizationPipeline(adapters=adapters).detect_engine(game_dir).engine_type
    return EntryRepository(db).get_project(str(game_dir.resolve()), engine)


def extract_and_store(
    pipeline: LocalizationPipeline,
    game_dir: Path,
    db: Database,
    *,
    target_lang: str = "ar",
    project_name: str | None = None,
) -> tuple[list[LocalizationEntry], int]:
    """Detect → extract → normalize → persist. Returns (entries, project_id).

    Entries stored previously but absent from this extraction are marked
    OBSOLETE (history preserved, never reused).
    """
    context = PipelineContext(game_dir=game_dir, target_lang=target_lang)
    result = pipeline.extract(game_dir, context)
    repo = EntryRepository(db)
    engine = pipeline.detect_engine(game_dir).engine_type
    project = repo.ensure_project(
        project_name or game_dir.resolve().name, str(game_dir.resolve()), engine
    )
    repo.upsert_many(project.id, result.entries)
    repo.mark_obsolete_missing(project.id, {e.id for e in result.entries})
    return result.entries, project.id


def load_translation_memory(db: Database) -> dict[str, TMRecord]:
    """Fingerprint → TMRecord from ALL stored entries (cross-project TM).

    Only exact fingerprints (source text + speaker + context) match, so a
    translation is never reused when the surrounding context differs.
    FLAGGED and OBSOLETE entries are excluded; provenance travels with the
    record so reuse stays gated (see ``tm_reusable``).
    """
    repo = EntryRepository(db)
    memory: dict[str, TMRecord] = {}
    for entry in repo.list():
        if (
            entry.translated_text
            and entry.status is not EntryStatus.FLAGGED
            and entry.status is not EntryStatus.OBSOLETE
        ):
            memory.setdefault(
                entry.fingerprint,
                TMRecord(
                    text=entry.translated_text,
                    source=entry.translation_source,
                    provider=(
                        f"{entry.translation_provider}:{entry.translation_model}"
                        if entry.translation_provider and entry.translation_model
                        else None
                    ),
                    model=entry.translation_model,
                ),
            )
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
    reuse_machine_tm: bool = False,
    progress=None,  # optional callable(done: int, total: int)
) -> TranslationStats:
    """Translate entries with TM + cache + provider, then persist.

    Force semantics: ignore already-translated text, TM and cache reads;
    the provider is called again and provenance is overwritten with the
    current provider/model. Source extraction is never destructive.
    """
    cache = SQLiteCache(
        db, target_lang=target_lang, provider=provider.config.identity
    )
    memory = load_translation_memory(db)
    stage = RealTranslateStage(
        provider,
        cache=cache,
        memory=memory,
        force=force,
        reuse_machine_tm=reuse_machine_tm,
    )
    stats = stage.run(
        entries, source_lang=source_lang, target_lang=target_lang, progress=progress
    )
    if project_id is not None:
        EntryRepository(db).upsert_many(project_id, entries)
    return stats


def clear_project_translations(db: Database, project_id: int) -> int:
    """Wipe a project's translations for a clean-slate comparison run.

    Resets entries (obsolete history preserved) and drops the matching
    provider-cache rows so old text cannot return via cache hits. Returns
    the number of reset entries.
    """
    from almurrib.storage.cache import SQLiteCache

    repo = EntryRepository(db)
    count, fingerprints = repo.clear_translations(project_id)
    SQLiteCache(db).delete_for_fingerprints(fingerprints)
    return count


def export_translations(
    pipeline: LocalizationPipeline,
    game_dir: Path,
    db: Database,
    *,
    output_dir: Path,
    target_lang: str = "ar",
    project_id: int | None = None,
) -> list[Path]:
    """Generate Ren'Py translation files from stored translations.

    Scoped to ``project_id`` when given (no cross-project leakage);
    OBSOLETE entries are never exported.
    """
    engine = pipeline.detect_engine(game_dir).engine_type
    if engine.value != "renpy":
        from almurrib.core.errors import ExportError

        raise ExportError(
            f"export not implemented for engine '{engine.value}'",
            hint="only Ren'Py export is supported in Phase 1.",
        )
    from almurrib.engine_adapters.renpy.reinject import write_translation_patch

    repo = EntryRepository(db)
    entries = [
        e
        for e in repo.list(project_id=project_id)
        if e.translated_text and e.status is not EntryStatus.OBSOLETE
    ]
    return write_translation_patch(entries, target_lang=target_lang, output_dir=output_dir)
