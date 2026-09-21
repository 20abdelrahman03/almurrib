"""SQLite database handle and schema migrations.

Responsibilities of this module are *only*: open the database, apply
migrations, hand out connections. No business logic lives here, and no raw
SQL exists outside ``storage/``.

Schema versioning uses the simple, transparent ``schema_migrations`` table
approach: migrations are applied in order, each exactly once.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 4

# Ordered migrations: (version, sql). Never edit applied entries; append new.
MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            game_dir    TEXT NOT NULL,
            engine      TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (game_dir, engine)
        );

        CREATE TABLE IF NOT EXISTS localization_entries (
            id               TEXT PRIMARY KEY,        -- deterministic content hash
            project_id       INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            engine           TEXT NOT NULL,
            source_text      TEXT NOT NULL,
            translated_text  TEXT,
            speaker          TEXT,
            context          TEXT,
            status           TEXT NOT NULL DEFAULT 'untranslated',
            fingerprint      TEXT NOT NULL,           -- meaning hash (cache/TM)
            source_refs_json TEXT NOT NULL,           -- JSON list of SourceRef
            tags_json        TEXT NOT NULL DEFAULT '[]',
            qa_flags_json    TEXT NOT NULL DEFAULT '[]',
            metadata_json    TEXT NOT NULL DEFAULT '{}',
            model_version    INTEGER NOT NULL DEFAULT 1,
            updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_entries_project
            ON localization_entries (project_id);
        CREATE INDEX IF NOT EXISTS idx_entries_fingerprint
            ON localization_entries (fingerprint);
        CREATE INDEX IF NOT EXISTS idx_entries_status
            ON localization_entries (status);

        CREATE TABLE IF NOT EXISTS translation_cache (
            cache_key        TEXT PRIMARY KEY,        -- see core.cache.make_cache_key
            entry_fingerprint TEXT NOT NULL,
            source_text      TEXT NOT NULL,
            translated_text  TEXT,
            target_lang      TEXT NOT NULL,
            provider         TEXT NOT NULL,
            engine           TEXT NOT NULL,
            updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_cache_fingerprint
            ON translation_cache (entry_fingerprint);
        """,
    ),
    (
        2,
        """
        -- Translation provenance (Phase 1 hardening): every stored
        -- translation records WHERE it came from so machine output can never
        -- silently masquerade as human-approved text.
        ALTER TABLE localization_entries
            ADD COLUMN translation_provider TEXT;
        ALTER TABLE localization_entries
            ADD COLUMN translation_model TEXT;
        ALTER TABLE localization_entries
            ADD COLUMN translation_source TEXT NOT NULL DEFAULT 'machine';
        """,
    ),
    (
        3,
        """
        -- Project/global terminology (Phase 2b): project_id 0 = shared.
        CREATE TABLE IF NOT EXISTS glossary_entries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id       INTEGER NOT NULL DEFAULT 0,
            source_term      TEXT NOT NULL,
            target_term      TEXT NOT NULL,
            type             TEXT NOT NULL DEFAULT 'term',
            gender           TEXT,
            style            TEXT,
            pronunciation    TEXT,
            notes            TEXT,
            aliases_json     TEXT NOT NULL DEFAULT '[]',
            forbidden_json   TEXT NOT NULL DEFAULT '[]',
            enabled          INTEGER NOT NULL DEFAULT 1,
            updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_glossary_term
            ON glossary_entries (project_id, source_term);
        CREATE INDEX IF NOT EXISTS idx_glossary_project
            ON glossary_entries (project_id);
        """,
    ),
    (
        4,
        """
        -- Entry identity is (project_id, id), not id alone: two different
        -- games can hold the identical relative path + line + text (same
        -- content hash). Sharing one row across projects corrupted project
        -- scoping (counts, lists, translations leaking between games).
        -- SQLite cannot alter a PK in place, so rebuild the table.
        CREATE TABLE localization_entries_new (
            id               TEXT NOT NULL,       -- deterministic content hash
            project_id       INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            engine           TEXT NOT NULL,
            source_text      TEXT NOT NULL,
            translated_text  TEXT,
            speaker          TEXT,
            context          TEXT,
            status           TEXT NOT NULL DEFAULT 'untranslated',
            fingerprint      TEXT NOT NULL,
            source_refs_json TEXT NOT NULL,
            tags_json        TEXT NOT NULL DEFAULT '[]',
            qa_flags_json    TEXT NOT NULL DEFAULT '[]',
            metadata_json    TEXT NOT NULL DEFAULT '{}',
            model_version    INTEGER NOT NULL DEFAULT 1,
            translation_provider TEXT,
            translation_model TEXT,
            translation_source TEXT NOT NULL DEFAULT 'machine',
            updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (project_id, id)
        );

        -- Pre-v4 duplicates (same id, several projects): keep the earliest
        -- stored row deterministically, drop the shadows. Explicit column
        -- lists: v2 appended provenance columns AFTER updated_at, so
        -- positional SELECT * would misalign.
        INSERT INTO localization_entries_new (
            id, project_id, engine, source_text, translated_text, speaker,
            context, status, fingerprint, source_refs_json, tags_json,
            qa_flags_json, metadata_json, model_version,
            translation_provider, translation_model, translation_source,
            updated_at
        )
            SELECT
                id, project_id, engine, source_text, translated_text, speaker,
                context, status, fingerprint, source_refs_json, tags_json,
                qa_flags_json, metadata_json, model_version,
                translation_provider, translation_model, translation_source,
                updated_at
            FROM localization_entries
            WHERE rowid IN (
                SELECT MIN(rowid) FROM localization_entries GROUP BY id
            );

        DROP TABLE localization_entries;
        ALTER TABLE localization_entries_new RENAME TO localization_entries;

        CREATE INDEX idx_entries_project
            ON localization_entries (project_id);
        CREATE INDEX idx_entries_fingerprint
            ON localization_entries (fingerprint);
        CREATE INDEX idx_entries_status
            ON localization_entries (status);
        """,
    ),
]


class Database:
    """Thin wrapper over an SQLite connection with migration support."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        # WAL keeps bulk upserts fast and readers non-blocking; it is a
        # per-database file mode, fully portable SQLite (no extra deps).
        # On :memory: this is a harmless no-op (stays 'memory').
        try:
            self._conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.Error:
            pass
        self._migrate()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def _migrate(self) -> None:
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        applied = {
            row[0] for row in self._conn.execute("SELECT version FROM schema_migrations")
        }
        for version, sql in MIGRATIONS:
            if version in applied:
                continue
            self._conn.executescript(sql)
            self._conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))
        self._conn.commit()

    def schema_version(self) -> int:
        row = self._conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0] or 0)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
