"""Repository over ``localization_entries`` (all entry SQL lives here).

The rest of the application never writes SQL — it talks to
:class:`EntryRepository` in terms of the domain model. Because entry ids are
deterministic content hashes, ``upsert`` makes re-extraction idempotent:
unchanged text lands in the same row; changed text creates a new row while
the old one can later be marked obsolete by a reconciliation pass.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
)


@dataclass
class Project:
    id: int
    name: str
    game_dir: str
    engine: EngineType


class EntryRepository:
    def __init__(self, db: "Database | sqlite3.Connection") -> None:
        # Accept either a Database or a bare connection for testability.
        self._conn = db.connection if hasattr(db, "connection") else db

    # ----- projects -----------------------------------------------------

    def ensure_project(self, name: str, game_dir: str, engine: EngineType) -> Project:
        self._conn.execute(
            "INSERT OR IGNORE INTO projects (name, game_dir, engine) VALUES (?, ?, ?)",
            (name, game_dir, engine.value),
        )
        row = self._conn.execute(
            "SELECT id, name, game_dir, engine FROM projects WHERE game_dir = ? AND engine = ?",
            (game_dir, engine.value),
        ).fetchone()
        self._conn.commit()
        return Project(id=int(row["id"]), name=row["name"], game_dir=row["game_dir"],
                       engine=EngineType(row["engine"]))

    # ----- entries ------------------------------------------------------

    def upsert(self, project_id: int, entry: LocalizationEntry) -> None:
        self._conn.execute(
            """
            INSERT INTO localization_entries (
                id, project_id, engine, source_text, translated_text, speaker,
                context, status, fingerprint, source_refs_json, tags_json,
                qa_flags_json, metadata_json, model_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                translated_text = COALESCE(excluded.translated_text, translated_text),
                status          = excluded.status,
                qa_flags_json   = excluded.qa_flags_json,
                metadata_json   = excluded.metadata_json,
                updated_at      = datetime('now')
            """,
            (
                entry.id,
                project_id,
                entry.engine.value,
                entry.source_text,
                entry.translated_text,
                entry.speaker,
                entry.context,
                entry.status.value,
                entry.fingerprint,
                json.dumps([r.to_dict() for r in entry.source_refs], ensure_ascii=False),
                json.dumps(entry.tags, ensure_ascii=False),
                json.dumps(entry.qa_flags, ensure_ascii=False),
                json.dumps(entry.metadata, ensure_ascii=False),
                entry.version,
            ),
        )
        self._conn.commit()

    def upsert_many(self, project_id: int, entries: list[LocalizationEntry]) -> int:
        for entry in entries:
            self.upsert(project_id, entry)
        return len(entries)

    def get(self, entry_id: str) -> LocalizationEntry | None:
        row = self._conn.execute(
            "SELECT * FROM localization_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def list(
        self,
        project_id: int | None = None,
        status: EntryStatus | None = None,
        limit: int | None = None,
    ) -> list[LocalizationEntry]:
        sql = "SELECT * FROM localization_entries"
        clauses, params = [], []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY source_refs_json, id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def count(self, project_id: int | None = None) -> int:
        if project_id is None:
            row = self._conn.execute("SELECT COUNT(*) FROM localization_entries").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM localization_entries WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return int(row[0])

    def find_by_fingerprint(self, fingerprint: str) -> list[LocalizationEntry]:
        rows = self._conn.execute(
            "SELECT * FROM localization_entries WHERE fingerprint = ?", (fingerprint,)
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    # ----- mapping ------------------------------------------------------

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> LocalizationEntry:
        return LocalizationEntry(
            id=row["id"],
            engine=EngineType(row["engine"]),
            source_text=row["source_text"],
            translated_text=row["translated_text"],
            speaker=row["speaker"],
            context=row["context"],
            status=EntryStatus(row["status"]),
            source_refs=[SourceRef.from_dict(r) for r in json.loads(row["source_refs_json"])],
            tags=json.loads(row["tags_json"]),
            qa_flags=json.loads(row["qa_flags_json"]),
            metadata=json.loads(row["metadata_json"]),
            version=int(row["model_version"]),
        )
