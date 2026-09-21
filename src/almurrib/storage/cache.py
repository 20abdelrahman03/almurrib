"""SQLite-backed persistent translation cache.

Same deterministic key scheme as the in-memory
:class:`almurrib.core.cache.TranslationCache`, but survives across runs.
This is what the future translation providers will consult before calling
any model or API.
"""

from __future__ import annotations

import sqlite3

from almurrib.core.cache import CacheRecord, DEFAULT_PROVIDER, make_cache_key
from almurrib.core.model import EngineType, LocalizationEntry


class SQLiteCache:
    def __init__(
        self,
        db: "Database | sqlite3.Connection",
        *,
        target_lang: str = "ar",
        provider: str = DEFAULT_PROVIDER,
    ) -> None:
        self._conn = db.connection if hasattr(db, "connection") else db
        self.target_lang = target_lang
        self.provider = provider

    def key_for(self, entry: LocalizationEntry) -> str:
        return make_cache_key(entry, target_lang=self.target_lang, provider=self.provider)

    def lookup(self, entry: LocalizationEntry) -> CacheRecord | None:
        row = self._conn.execute(
            "SELECT * FROM translation_cache WHERE cache_key = ?",
            (self.key_for(entry),),
        ).fetchone()
        if row is None:
            return None
        return CacheRecord(
            key=row["cache_key"],
            source_text=row["source_text"],
            translated_text=row["translated_text"],
            target_lang=row["target_lang"],
            provider=row["provider"],
            engine=EngineType(row["engine"]),
        )

    def remember(self, entry: LocalizationEntry, translated_text: str | None) -> CacheRecord:
        key = self.key_for(entry)
        self._conn.execute(
            """
            INSERT INTO translation_cache (
                cache_key, entry_fingerprint, source_text, translated_text,
                target_lang, provider, engine
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                translated_text = excluded.translated_text,
                updated_at      = datetime('now')
            """,
            (
                key,
                entry.fingerprint,
                entry.source_text,
                translated_text,
                self.target_lang,
                self.provider,
                entry.engine.value,
            ),
        )
        self._conn.commit()
        return CacheRecord(
            key=key,
            source_text=entry.source_text,
            translated_text=translated_text,
            target_lang=self.target_lang,
            provider=self.provider,
            engine=entry.engine,
        )

    def __len__(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM translation_cache").fetchone()
        return int(row[0])

    def delete_for_fingerprints(self, fingerprints: set[str]) -> int:
        """Drop cached rows for the given meaning-hashes (clean-slate runs).

        Fingerprints are meaning-scoped, so sibling projects sharing an
        identical line lose that cached row too — it rebuilds on next use.
        """
        if not fingerprints:
            return 0
        with self._conn:
            cursor = self._conn.executemany(
                "DELETE FROM translation_cache WHERE entry_fingerprint = ?",
                [(fp,) for fp in fingerprints],
            )
        return cursor.rowcount if cursor.rowcount is not None else 0
