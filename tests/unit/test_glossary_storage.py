"""Glossary storage tests (migration v3, conflicts, scoping)."""

from almurrib.core.errors import StorageError
from almurrib.core.glossary import Glossary, GlossaryEntry
from almurrib.storage.database import Database, SCHEMA_VERSION
from almurrib.storage.glossary import GlossaryRepository


def test_migration_v3_table(tmp_path):
    with Database(tmp_path / "g.db") as db:
        assert db.schema_version() == SCHEMA_VERSION
        cols = {r[1] for r in db.connection.execute(
            "PRAGMA table_info(glossary_entries)").fetchall()}
        assert {"source_term", "target_term", "type", "aliases_json",
                "enabled", "project_id"} <= cols


def test_add_round_trip_and_scoping(tmp_path):
    with Database(tmp_path / "g.db") as db:
        repo = GlossaryRepository(db)
        repo.add(GlossaryEntry(source_term="Sylvie", target_term="سيلفي",
                               type="character", gender="female", project_id=0))
        repo.add(GlossaryEntry(source_term="Sylvie", target_term="سيلفي-خاص",
                               project_id=9))
        assert len(repo.list()) == 2
        scoped = repo.for_project(9)
        by_term = {e.source_term: e.target_term for e in scoped.enabled()}
        assert by_term["Sylvie"] == "سيلفي-خاص"  # project wins
        assert len(repo.for_project(10).enabled()) == 1  # global only


def test_conflict_rejected_identical_ok(tmp_path):
    with Database(tmp_path / "g.db") as db:
        repo = GlossaryRepository(db)
        repo.add(GlossaryEntry(source_term="Sylvie", target_term="سيلفي"))
        repo.add(GlossaryEntry(source_term="Sylvie", target_term="سيلفي"))
        import pytest

        with pytest.raises(StorageError):
            repo.add(GlossaryEntry(source_term="SYLVIE", target_term="غير"))
        with pytest.raises(StorageError):
            repo.add(GlossaryEntry(source_term="Sylvie", target_term="غير"))
        assert len(repo.list()) == 1


def test_remove_and_clear(tmp_path):
    with Database(tmp_path / "g.db") as db:
        repo = GlossaryRepository(db)
        repo.add(GlossaryEntry(source_term="A", target_term="1"))
        repo.add(GlossaryEntry(source_term="B", target_term="2", project_id=5))
        assert repo.remove(0, "a") is True  # case-insensitive
        assert repo.remove(0, "missing") is False
        assert repo.clear(5) == 1
        assert len(repo.list()) == 0


def test_add_many_reports_conflicts(tmp_path):
    with Database(tmp_path / "g.db") as db:
        repo = GlossaryRepository(db)
        glossary = Glossary([
            GlossaryEntry(source_term="A", target_term="1"),
            GlossaryEntry(source_term="A", target_term="2"),
        ])
        added, skipped = repo.add_many(glossary)
        assert added == 1
        assert len(skipped) == 1
