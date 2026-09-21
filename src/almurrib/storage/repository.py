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

    def get_project(self, game_dir: str, engine: EngineType) -> Project | None:
        """Look up an existing project without creating one (scoping aid)."""
        row = self._conn.execute(
            "SELECT id, name, game_dir, engine FROM projects WHERE game_dir = ? AND engine = ?",
            (game_dir, engine.value),
        ).fetchone()
        if row is None:
            return None
        return Project(id=int(row["id"]), name=row["name"], game_dir=row["game_dir"],
                       engine=EngineType(row["engine"]))

    # ----- entries ------------------------------------------------------

    # Lifecycle rule for re-extraction (keeps text/status coherent):
    # * fresh entry WITHOUT translation + stored translation present
    #   -> keep stored text, status, QA flags and provenance (idempotent).
    # * fresh entry WITH translation (e.g. existing game translation pairs)
    #   -> take the text, but never demote a human REVIEWED/APPROVED state.
    # Structural info (refs/tags/metadata) always refreshes.
    _UPSERT_SQL = """
            INSERT INTO localization_entries (
                id, project_id, engine, source_text, translated_text, speaker,
                context, status, fingerprint, source_refs_json, tags_json,
                qa_flags_json, metadata_json, model_version,
                translation_provider, translation_model, translation_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, id) DO UPDATE SET
                translated_text = COALESCE(excluded.translated_text, translated_text),
                status = CASE
                    WHEN excluded.translated_text IS NULL
                         AND translated_text IS NOT NULL
                        THEN status
                    WHEN excluded.translated_text IS NOT NULL
                         AND status IN ('reviewed', 'approved')
                        THEN status
                    ELSE excluded.status
                END,
                qa_flags_json = CASE
                    WHEN excluded.translated_text IS NULL
                         AND translated_text IS NOT NULL
                        THEN qa_flags_json
                    ELSE excluded.qa_flags_json
                END,
                translation_provider = CASE
                    WHEN excluded.translated_text IS NULL
                         AND translated_text IS NOT NULL
                        THEN translation_provider
                    ELSE excluded.translation_provider
                END,
                translation_model = CASE
                    WHEN excluded.translated_text IS NULL
                         AND translated_text IS NOT NULL
                        THEN translation_model
                    ELSE excluded.translation_model
                END,
                translation_source = CASE
                    WHEN excluded.translated_text IS NULL
                         AND translated_text IS NOT NULL
                        THEN translation_source
                    ELSE excluded.translation_source
                END,
                source_refs_json = excluded.source_refs_json,
                tags_json        = excluded.tags_json,
                metadata_json    = excluded.metadata_json,
                updated_at       = datetime('now')
            """

    def _entry_params(self, project_id: int, entry: LocalizationEntry) -> tuple:
        return (
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
            entry.translation_provider,
            entry.translation_model,
            entry.translation_source,
        )

    def upsert(self, project_id: int, entry: LocalizationEntry) -> None:
        self._conn.execute(self._UPSERT_SQL, self._entry_params(project_id, entry))
        self._conn.commit()

    def upsert_many(self, project_id: int, entries: list[LocalizationEntry]) -> int:
        # Single transaction for the whole batch: N entries, 1 commit.
        # Rolls back cleanly on failure instead of half-persisting.
        with self._conn:
            self._conn.executemany(
                self._UPSERT_SQL,
                [self._entry_params(project_id, e) for e in entries],
            )
        return len(entries)

    def clear_translations(self, project_id: int) -> tuple[int, set[str]]:
        """Reset a project for a fresh translation run.

        Clears translated text, QA flags and provenance on current (non
        obsolete) entries; OBSOLETE history is preserved untouched. Returns
        (reset_count, fingerprints) — fingerprints let the caller drop the
        matching cache rows so cleared text cannot sneak back via cache.
        """
        rows = self._conn.execute(
            "SELECT id, fingerprint FROM localization_entries "
            "WHERE project_id = ? AND status != 'obsolete' "
            "AND translated_text IS NOT NULL",
            (project_id,),
        ).fetchall()
        if not rows:
            return 0, set()
        fingerprints = {r["fingerprint"] for r in rows}
        with self._conn:
            self._conn.executemany(
                "UPDATE localization_entries SET translated_text = NULL,"
                " status = 'untranslated', qa_flags_json = '[]',"
                " translation_provider = NULL, translation_model = NULL,"
                " translation_source = 'machine',"
                " updated_at = datetime('now') WHERE id = ?",
                [(r["id"],) for r in rows],
            )
        return len(rows), fingerprints

    def mark_obsolete_missing(
        self, project_id: int, current_ids: set[str]
    ) -> int:
        """Mark stored entries absent from a fresh extraction as OBSOLETE.

        History (text + provenance) is preserved; obsolete rows are excluded
        from translation, TM and export by their callers. Returns the count
        of newly marked rows.
        """
        rows = self._conn.execute(
            "SELECT id, status FROM localization_entries WHERE project_id = ?",
            (project_id,),
        ).fetchall()
        stale = [
            r["id"] for r in rows
            if r["id"] not in current_ids and r["status"] != EntryStatus.OBSOLETE.value
        ]
        if not stale:
            return 0
        with self._conn:
            self._conn.executemany(
                "UPDATE localization_entries SET status = 'obsolete',"
                " updated_at = datetime('now') WHERE id = ?",
                [(i,) for i in stale],
            )
        return len(stale)

    def upsert_for_entries(self, entries: list[LocalizationEntry]) -> int:
        """Persist entries against their originating project(s).

        Used when re-saving entries that already exist in the database
        (e.g. after translation) without needing the project id at hand.
        An id shared by several projects (identical content) updates every
        matching row — identical content means identical state.
        """
        count = 0
        for entry in entries:
            rows = self._conn.execute(
                "SELECT project_id FROM localization_entries WHERE id = ?",
                (entry.id,),
            ).fetchall()
            for row in rows:
                self.upsert(int(row["project_id"]), entry)
                count += 1
        return count

    def get(self, entry_id: str,
            project_id: int | None = None) -> LocalizationEntry | None:
        if project_id is None:
            row = self._conn.execute(
                "SELECT * FROM localization_entries WHERE id = ? "
                "ORDER BY project_id LIMIT 1",
                (entry_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM localization_entries WHERE id = ? AND project_id = ?",
                (entry_id, project_id),
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
        # translation_* columns exist since schema v2; tolerate v1 rows.
        def _col(name: str, default=None):
            try:
                return row[name]
            except (KeyError, IndexError):
                return default

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
            translation_provider=_col("translation_provider"),
            translation_model=_col("translation_model"),
            translation_source=_col("translation_source") or "machine",
        )
