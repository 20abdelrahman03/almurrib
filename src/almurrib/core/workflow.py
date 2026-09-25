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
from almurrib.core.translate import (
    PreflightEstimate,
    RealTranslateStage,
    TMRecord,
    TranslationStats,
    estimate_preflight,
    run_canary,
)
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


def load_glossary(db: Database, project_id: int | None = None) -> "Glossary":
    """Project + global glossary merged (project wins on conflict)."""
    from almurrib.core.glossary import GLOBAL_PROJECT_ID, Glossary
    from almurrib.storage.glossary import GlossaryRepository

    repo = GlossaryRepository(db)
    if project_id is None:
        global_only = Glossary([e for e in repo.list()
                                if e.project_id == GLOBAL_PROJECT_ID])
        return global_only
    return repo.for_project(project_id)


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
    glossary: "Glossary | None | bool" = None,
    progress=None,  # optional callable(accepted: int, total: int)
    log=None,  # optional callable(message: str) for milestone lines
    canary: bool | None = None,  # None = auto for large jobs (>100 pending)
    persist_per_chunk: bool = True,  # durable progress for pause/stop/crash
    stop_event=None,  # duck-typed threading.Event: graceful stop (§29)
    pause_event=None,  # duck-typed threading.Event: wait while set (§29)
) -> TranslationStats:
    """Translate entries with TM + cache + provider, then persist.

    Force semantics: ignore already-translated text, TM and cache reads;
    the provider is called again and provenance is overwritten with the
    current provider/model. Source extraction is never destructive.

    ``glossary``: None = auto-load project+global glossary from the DB;
    False = disable glossary entirely; a Glossary = use as given. A
    non-empty glossary scopes the cache (``:g<rev>`` suffix) so edited
    glossaries cannot silently serve stale cached text.
    """
    from almurrib.core.glossary import GLOBAL_PROJECT_ID, Glossary

    if glossary is None:
        glossary = load_glossary(db, project_id)
    elif glossary is False:
        glossary = Glossary()
    # No cache-identity suffix: per-hit glossary vetoes (see
    # RealTranslateStage._glossary_veto) invalidate precisely the entries
    # whose cached text violates the active glossary, keeping unrelated
    # cache hits stable across glossary edits.
    cache = SQLiteCache(
        db, target_lang=target_lang, provider=provider.config.identity
    )
    memory = load_translation_memory(db)
    # Canary gate (§3 of the incident): prove the provider on 3 entries
    # before a large job spends tokens. Auto for >100 pending entries.
    pending_probe = [e for e in entries
                     if e.status is not EntryStatus.OBSOLETE
                     and not e.translated_text]
    if canary is None:
        canary = len(pending_probe) > 100
    if canary and pending_probe:
        result = run_canary(
            pending_probe, provider=provider, source_lang=source_lang,
            target_lang=target_lang, glossary=glossary, log=log,
            cache=cache)
        if not result.passed:
            from almurrib.core.errors import TranslationAbortedError

            raise TranslationAbortedError(
                f"canary FAILED ({result.accepted}/{result.tested} accepted) "
                f"[{result.category}]: {result.error} — full run blocked "
                "before spending tokens.",
                hint="fix the provider/model/key, then re-run.",
            )
    stage = RealTranslateStage(
        provider,
        cache=cache,
        memory=memory,
        force=force,
        reuse_machine_tm=reuse_machine_tm,
        glossary=glossary,
    )
    repo = EntryRepository(db)
    persist_cb = None
    if project_id is not None and persist_per_chunk:
        def persist_cb(chunk_entries, _repo=repo, _pid=project_id):
            _repo.upsert_many(_pid, chunk_entries)
    stats = stage.run(
        entries, source_lang=source_lang, target_lang=target_lang,
        progress=progress, log=log,
        persist=persist_cb, stop_event=stop_event, pause_event=pause_event,
    )
    if project_id is not None:
        EntryRepository(db).upsert_many(project_id, entries)
    return stats


def dry_run_report(
    entries: list[LocalizationEntry],
    db: Database,
    provider,
    *,
    source_lang: str = "en",
    target_lang: str = "ar",
    project_id: int | None = None,
    log=None,
) -> PreflightEstimate:
    """Preflight without spending full-run tokens (§12 of the incident).

    Reports counts + measured token estimate + runs the 3-entry canary
    (the only calls spent). Never translates the project.
    """
    from almurrib.core.glossary import Glossary

    from almurrib.storage.cache import SQLiteCache

    glossary = load_glossary(db, project_id)
    estimate = estimate_preflight(
        entries, provider=provider, source_lang=source_lang,
        target_lang=target_lang, glossary=glossary, log=log)
    pending_probe = [e for e in entries
                     if e.status is not EntryStatus.OBSOLETE
                     and not e.translated_text]
    cache = SQLiteCache(
        db, target_lang=target_lang, provider=provider.config.identity)
    estimate.canary = run_canary(
        pending_probe, provider=provider, source_lang=source_lang,
        target_lang=target_lang, glossary=glossary or Glossary(), log=log,
        cache=cache)
    return estimate


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
    """Generate engine output files from stored translations.

    Scoped to ``project_id`` when given (no cross-project leakage);
    OBSOLETE entries are never exported. Engine branching lives in
    ``engine_adapters.export`` (never in core).
    """
    from almurrib.engine_adapters.export import export_for_engine

    engine = pipeline.detect_engine(game_dir).engine_type
    return export_for_engine(
        engine, game_dir, db, output_dir=output_dir,
        target_lang=target_lang, project_id=project_id)
