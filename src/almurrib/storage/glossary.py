"""Glossary persistence (project-scoped + global, same database).

Terms live in ``glossary_entries`` next to translations — no second
database. ``project_id`` 0 means shared/global. Conflicts (same source
term, different target, case-insensitive) are rejected loudly at add and
import time, never merged silently.
"""

from __future__ import annotations

import json
import sqlite3

from almurrib.core.errors import StorageError
from almurrib.core.glossary import GLOBAL_PROJECT_ID, Glossary, GlossaryEntry


class GlossaryRepository:
    def __init__(self, db: "Database | sqlite3.Connection") -> None:
        self._conn = db.connection if hasattr(db, "connection") else db

    # ----- reads --------------------------------------------------------

    def list(self, project_id: int | None = None) -> list[GlossaryEntry]:
        if project_id is None:
            rows = self._conn.execute(
                "SELECT * FROM glossary_entries ORDER BY source_term"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM glossary_entries WHERE project_id IN (0, ?) "
                "ORDER BY source_term",
                (project_id,),
            ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def for_project(self, project_id: int) -> Glossary:
        """Project + global entries merged (project wins on conflict)."""
        from almurrib.core.glossary import merge_glossaries

        project = Glossary([e for e in self.list(project_id)
                            if e.project_id == project_id])
        shared = Glossary([e for e in self.list(project_id)
                           if e.project_id == GLOBAL_PROJECT_ID])
        return merge_glossaries(project, shared)

    # ----- writes ---------------------------------------------------------

    def add(self, entry: GlossaryEntry) -> GlossaryEntry:
        """Insert one entry; conflicting duplicates raise StorageError."""
        clash = self._conn.execute(
            "SELECT target_term FROM glossary_entries "
            "WHERE project_id = ? AND source_term = ? COLLATE NOCASE",
            (entry.project_id, entry.source_term),
        ).fetchone()
        if clash is not None and str(clash["target_term"]) != entry.target_term:
            raise StorageError(
                f"glossary conflict for '{entry.source_term}': "
                f"'{clash['target_term']}' vs '{entry.target_term}'",
                hint="disable or remove the old entry first.",
            )
        if clash is not None:
            return entry  # identical duplicate: idempotent no-op
        cursor = self._conn.execute(
            """
            INSERT INTO glossary_entries (
                project_id, source_term, target_term, type, gender, style,
                pronunciation, notes, aliases_json, forbidden_json, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.project_id,
                entry.source_term,
                entry.target_term,
                entry.type,
                entry.gender,
                entry.style,
                entry.pronunciation,
                entry.notes,
                json.dumps(list(entry.aliases), ensure_ascii=False),
                json.dumps(list(entry.forbidden), ensure_ascii=False),
                1 if entry.enabled else 0,
            ),
        )
        self._conn.commit()
        return GlossaryEntry(**{**entry.to_dict(), "id": cursor.lastrowid,
                                "project_id": entry.project_id})

    def add_many(self, glossary: Glossary) -> tuple[int, list[dict]]:
        """Insert many; returns (added_count, skipped_conflicts)."""
        added, skipped = 0, []
        for entry in glossary.entries:
            try:
                self.add(entry)
                added += 1
            except StorageError as exc:
                skipped.append({"term": entry.source_term,
                                "reason": exc.message})
        return added, skipped

    def remove(self, project_id: int, source_term: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM glossary_entries "
            "WHERE project_id = ? AND source_term = ? COLLATE NOCASE",
            (project_id, source_term),
        )
        self._conn.commit()
        return (cursor.rowcount or 0) > 0

    def clear(self, project_id: int | None = None) -> int:
        if project_id is None:
            cursor = self._conn.execute("DELETE FROM glossary_entries")
        else:
            cursor = self._conn.execute(
                "DELETE FROM glossary_entries WHERE project_id = ?",
                (project_id,),
            )
        self._conn.commit()
        return cursor.rowcount or 0

    # ----- mapping --------------------------------------------------------

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> GlossaryEntry:
        return GlossaryEntry(
            source_term=row["source_term"],
            target_term=row["target_term"],
            type=row["type"],
            gender=row["gender"],
            style=row["style"],
            pronunciation=row["pronunciation"],
            notes=row["notes"],
            aliases=tuple(json.loads(row["aliases_json"])),
            forbidden=tuple(json.loads(row["forbidden_json"])),
            enabled=bool(row["enabled"]),
            project_id=int(row["project_id"]),
            id=int(row["id"]),
        )
