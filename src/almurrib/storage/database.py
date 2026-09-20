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

SCHEMA_VERSION = 1

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
