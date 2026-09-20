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
