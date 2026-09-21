"""SQLite persistence tests."""

from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
)
from almurrib.storage.database import Database, SCHEMA_VERSION
from almurrib.storage.repository import EntryRepository


def _entry(text: str, line: int, speaker: str | None = None) -> LocalizationEntry:
    ref = SourceRef(file="game/script.rpy", line=line, statement="say")
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY,
        source_text=text,
        speaker=speaker,
        source_refs=[ref],
    )


def test_migrations_applied(tmp_path):
    with Database(tmp_path / "test.db") as db:
        assert db.schema_version() == SCHEMA_VERSION
        row = db.connection.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"


def test_provenance_columns_exist_with_defaults(tmp_path):
    with Database(tmp_path / "test.db") as db:
        cols = {r[1] for r in db.connection.execute(
            "PRAGMA table_info(localization_entries)").fetchall()}
        assert {"translation_provider", "translation_model",
                "translation_source"} <= cols
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)
        repo.upsert(project.id, _entry("Hello!", 9))
        loaded = repo.get(_entry("Hello!", 9).id)
        assert loaded.translation_source == "machine"
        assert loaded.translation_provider is None


def test_upsert_and_round_trip(tmp_path):
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)
        entry = _entry("Hello!", 9, speaker="Eileen")
        repo.upsert(project.id, entry)

        loaded = repo.get(entry.id)
        assert loaded is not None
        assert loaded.source_text == "Hello!"
        assert loaded.speaker == "Eileen"
        assert loaded.status == EntryStatus.UNTRANSLATED
        assert loaded.source_refs[0].file == "game/script.rpy"


def test_reextraction_is_idempotent(tmp_path):
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)
        entries = [_entry("Hello!", 9), _entry("Bye!", 10)]
        repo.upsert_many(project.id, entries)
        repo.upsert_many(project.id, entries)  # same extraction again
        assert repo.count(project.id) == 2


def test_translation_survives_reextraction(tmp_path):
    """An existing translation must not be wiped by a later re-extract."""
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)

        translated = _entry("Hello!", 9)
        translated.translated_text = "مرحباً!"
        translated.status = EntryStatus.TRANSLATED
        repo.upsert(project.id, translated)

        fresh = _entry("Hello!", 9)  # re-extracted: no translation
        repo.upsert(project.id, fresh)

        loaded = repo.get(translated.id)
        assert loaded.translated_text == "مرحباً!"


def test_reextraction_preserves_status_and_provenance(tmp_path):
    """Fresh extract without translation must not reset a translated row."""
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)

        translated = _entry("Hello!", 9)
        translated.translated_text = "مرحباً!"
        translated.status = EntryStatus.TRANSLATED
        translated.translation_provider = "openai_compat"
        translated.translation_model = "m"
        translated.translation_source = "machine"
        repo.upsert(project.id, translated)

        repo.upsert(project.id, _entry("Hello!", 9))  # fresh, untranslated
        loaded = repo.get(translated.id)
        assert loaded.translated_text == "مرحباً!"
        assert loaded.status is EntryStatus.TRANSLATED
        assert loaded.translation_model == "m"
        assert loaded.qa_flags == []


def test_human_review_not_demoted_by_reextraction(tmp_path):
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)

        reviewed = _entry("Hello!", 9)
        reviewed.translated_text = "مرحباً!"
        reviewed.status = EntryStatus.REVIEWED
        repo.upsert(project.id, reviewed)

        incoming = _entry("Hello!", 9)
        incoming.translated_text = "ترجمة أخرى"
        incoming.status = EntryStatus.TRANSLATED
        repo.upsert(project.id, incoming)

        loaded = repo.get(reviewed.id)
        assert loaded.status is EntryStatus.REVIEWED
        assert loaded.translated_text == "ترجمة أخرى"


def test_mark_obsolete_missing_preserves_history(tmp_path):
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)
        repo.upsert_many(project.id, [_entry("Keep", 1), _entry("Gone", 2)])

        keep_id = _entry("Keep", 1).id
        marked = repo.mark_obsolete_missing(project.id, {keep_id})
        assert marked == 1
        assert repo.get(_entry("Gone", 2).id).status is EntryStatus.OBSOLETE
        assert repo.get(keep_id).status is EntryStatus.UNTRANSLATED
        # second call is stable (no double counting)
        assert repo.mark_obsolete_missing(project.id, {keep_id}) == 0


def test_clear_translations_resets_but_preserves_obsolete(tmp_path):
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)

        done = _entry("Hello!", 9)
        done.translated_text = "مرحباً!"
        done.status = EntryStatus.TRANSLATED
        done.translation_provider = "openai_compat"
        done.qa_flags.append("placeholder_missing:x")
        repo.upsert(project.id, done)
        repo.upsert(project.id, _entry("Todo", 10))

        gone = _entry("Gone", 11)
        gone.translated_text = "قديم"
        gone.status = EntryStatus.TRANSLATED
        repo.upsert(project.id, gone)
        repo.mark_obsolete_missing(project.id, {done.id, _entry("Todo", 10).id})

        count, fingerprints = repo.clear_translations(project.id)
        assert count == 1  # only the current translated row
        assert fingerprints == {done.fingerprint}

        fresh = repo.get(done.id)
        assert fresh.translated_text is None
        assert fresh.status is EntryStatus.UNTRANSLATED
        assert fresh.qa_flags == []
        assert fresh.translation_provider is None
        # obsolete history untouched
        assert repo.get(gone.id).translated_text == "قديم"

        # second clear is a stable no-op
        assert repo.clear_translations(project.id) == (0, set())


def test_same_content_across_projects_stays_independent(tmp_path):
    """Identical (path, line, text) in two games: separate rows, states."""
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project_a = repo.ensure_project("A", "/games/a", EngineType.RENPY)
        project_b = repo.ensure_project("B", "/games/b", EngineType.RENPY)

        repo.upsert_many(project_a.id, [_entry("Hello!", 9)])
        repo.upsert_many(project_b.id, [_entry("Hello!", 9)])
        assert repo.count(project_a.id) == 1
        assert repo.count(project_b.id) == 1

        translated = _entry("Hello!", 9)
        translated.translated_text = "مرحباً!"
        translated.status = EntryStatus.TRANSLATED
        repo.upsert(project_a.id, translated)

        assert repo.get(translated.id, project_a.id).translated_text == "مرحباً!"
        assert repo.get(translated.id, project_b.id).translated_text is None
        assert repo.get(translated.id, project_b.id).status is EntryStatus.UNTRANSLATED

        # Re-extracting B never adopts or disturbs A's translation.
        repo.upsert_many(project_b.id, [_entry("Hello!", 9)])
        assert repo.get(translated.id, project_a.id).translated_text == "مرحباً!"


def test_migration_preserves_provenance_columns(tmp_path):
    """v4 rebuild keeps all 18 columns aligned (v2 appended after updated_at)."""
    with Database(tmp_path / "test.db") as db:
        assert db.schema_version() == 4
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)
        entry = _entry("Hello!", 9)
        entry.translated_text = "مرحباً!"
        entry.status = EntryStatus.TRANSLATED
        entry.translation_provider = "openai_compat"
        entry.translation_model = "m"
        entry.translation_source = "human"
        repo.upsert(project.id, entry)
        loaded = repo.get(entry.id, project.id)
        assert (loaded.translated_text, loaded.translation_provider,
                loaded.translation_model, loaded.translation_source) == \
            ("مرحباً!", "openai_compat", "m", "human")


def test_get_project_lookup(tmp_path):
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        assert repo.get_project("/nope", EngineType.RENPY) is None
        created = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)
        found = repo.get_project("/games/demo", EngineType.RENPY)
        assert found is not None and found.id == created.id


def test_list_filtering(tmp_path):
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)
        repo.upsert(project.id, _entry("A", 1))
        done = _entry("B", 2)
        done.status = EntryStatus.TRANSLATED
        repo.upsert(project.id, done)

        assert len(repo.list(status=EntryStatus.UNTRANSLATED)) == 1
        assert len(repo.list(status=EntryStatus.TRANSLATED)) == 1
        assert repo.count(project.id) == 2


def test_find_by_fingerprint(tmp_path):
    with Database(tmp_path / "test.db") as db:
        repo = EntryRepository(db)
        project = repo.ensure_project("demo", "/games/demo", EngineType.RENPY)
        entry = _entry("Hello!", 9)
        repo.upsert(project.id, entry)
        matches = repo.find_by_fingerprint(entry.fingerprint)
        assert [m.id for m in matches] == [entry.id]
