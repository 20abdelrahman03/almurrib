"""Repeated-run stability: same DB + same game must converge, not rot.

Covers: idempotent re-extraction, zero-API second runs, force semantics,
stable row counts, no duplicated export blocks, coherent statuses.
"""

from almurrib.core.model import EntryStatus
from almurrib.core.pipeline import LocalizationPipeline, PipelineContext
from almurrib.core.translate import RealTranslateStage
from almurrib.core.workflow import (
    export_translations,
    extract_and_store,
    translate_entries,
)
from almurrib.engine_adapters import default_adapters
from almurrib.providers.fake import FakeProvider
from almurrib.storage.database import Database
from almurrib.storage.repository import EntryRepository


def _fresh_db(path):
    return Database(path)


def test_four_runs_converge(renpy_fixture_dir, tmp_path):
    db_path = tmp_path / "stable.db"
    out = tmp_path / "patch"
    pipeline = LocalizationPipeline(adapters=default_adapters())
    context = PipelineContext(game_dir=renpy_fixture_dir)

    with _fresh_db(db_path) as db:
        # run 1: extract + translate (API work happens)
        entries, project_id = extract_and_store(pipeline, renpy_fixture_dir, db)
        stats1 = translate_entries(entries, db, FakeProvider(), project_id=project_id)
        assert stats1.api_translated == 10  # 11 entries, 1 pre-translated
        written1 = export_translations(pipeline, renpy_fixture_dir, db,
                                       output_dir=out, target_lang="arabic")
        assert written1
        content1 = (out / "game" / "tl" / "arabic" / "strings.rpy").read_text(
            encoding="utf-8")
        rows1 = EntryRepository(db).count(project_id)

        # run 2: re-extract + translate again -> zero API work
        entries2, project_id2 = extract_and_store(pipeline, renpy_fixture_dir, db)
        assert project_id2 == project_id
        stats2 = translate_entries(entries2, db, FakeProvider(),
                                   project_id=project_id)
        assert stats2.api_calls == 0
        assert stats2.api_translated == 0
        assert stats2.failed == 0
        assert EntryRepository(db).count(project_id) == rows1
        written2 = export_translations(pipeline, renpy_fixture_dir, db,
                                       output_dir=out, target_lang="arabic")
        content2 = (out / "game" / "tl" / "arabic" / "strings.rpy").read_text(
            encoding="utf-8")
        assert content2 == content1  # byte-stable export
        assert written2 == written1

        # run 3: translate-only -> everything already translated
        repo = EntryRepository(db)
        stats3 = translate_entries(repo.list(project_id=project_id), db,
                                   FakeProvider(), project_id=project_id)
        assert stats3.already_translated == len(entries2)
        assert stats3.api_calls == 0

        # run 4: force -> provider called again, same coherent outcome
        stats4 = translate_entries(repo.list(project_id=project_id), db,
                                   FakeProvider(), project_id=project_id,
                                   force=True)
        assert stats4.api_translated == len(entries2)
        assert stats4.failed == 0
        assert EntryRepository(db).count(project_id) == rows1
        for entry in repo.list(project_id=project_id):
            assert entry.status in (EntryStatus.TRANSLATED, EntryStatus.FLAGGED)
            assert entry.translated_text


def test_source_removal_marks_obsolete_not_deleted(renpy_fixture_dir, tmp_path):
    import shutil

    from almurrib.core.workflow import load_translation_memory

    # Work on a private copy: the real fixture is never modified.
    game_copy = tmp_path / "gamecopy"
    shutil.copytree(renpy_fixture_dir, game_copy)
    db_path = tmp_path / "obs.db"
    pipeline = LocalizationPipeline(adapters=default_adapters())
    with _fresh_db(db_path) as db:
        entries, project_id = extract_and_store(pipeline, game_copy, db)
        assert len(entries) == 11

        # Translate everything, then delete one translatable line.
        removed_text = "Your score is [score], {player_name}!"
        removed = next(e for e in entries if removed_text in e.source_text)
        stats = translate_entries(entries, db, FakeProvider(), project_id=project_id)
        assert stats.failed == 0
        script = game_copy / "game" / "script.rpy"
        kept = [ln for ln in script.read_text(encoding="utf-8").splitlines()
                if removed_text not in ln]
        assert len(kept) < len(script.read_text(encoding="utf-8").splitlines())
        script.write_text("\n".join(kept) + "\n", encoding="utf-8")

        entries2, project_id2 = extract_and_store(pipeline, game_copy, db)
        assert project_id2 == project_id
        assert len(entries2) == 10

        repo = EntryRepository(db)
        stale = repo.get(removed.id)
        assert stale.status is EntryStatus.OBSOLETE
        assert stale.translated_text  # history preserved, not deleted

        # Obsolete translations are invisible to TM and export.
        assert removed.fingerprint not in load_translation_memory(db)
        out = tmp_path / "patch"
        export_translations(pipeline, game_copy, db, output_dir=out,
                            target_lang="arabic", project_id=project_id)
        content = (out / "game" / "tl" / "arabic" / "strings.rpy").read_text(
            encoding="utf-8")
        assert removed.source_text not in content
