"""Deterministic translation cache.

Answers one question, cheaply and reproducibly:

    "Have we already processed this exact source text under this relevant
    context for this target language and provider configuration?"

Keying strategy (Phase 1 first half):

    cache_key = SHA-256( engine | source_text | speaker | context
                       | target_lang | provider )

* ``provider`` defaults to ``"identity"`` (no translation performed yet);
  once llama.cpp / cloud providers land, their name+model become part of
  the key so results from different providers never collide.
* The cache is storage-agnostic: :class:`TranslationCache` is an in-memory
  implementation used by the pipeline and tests; :class:`SQLiteCache` (in
  ``storage.cache``) persists across runs using the same key scheme.

Advanced AI-aware caching (semantic similarity, fuzzy reuse) is explicitly
out of scope for now — determinism first.
"""

from __future__ import annotations

from dataclasses import dataclass

from almurrib.core.model import EngineType, LocalizationEntry, content_hash

DEFAULT_PROVIDER = "identity"


def make_cache_key(
    entry: LocalizationEntry,
    *,
    target_lang: str,
    provider: str = DEFAULT_PROVIDER,
) -> str:
    """Build the deterministic cache key for an entry."""
    return content_hash(
        entry.engine.value,
        entry.source_text,
        entry.speaker,
        entry.context,
        target_lang,
        provider,
    )


@dataclass
class CacheRecord:
    key: str
    source_text: str
    translated_text: str | None
    target_lang: str
    provider: str = DEFAULT_PROVIDER
    engine: EngineType = EngineType.UNKNOWN


class TranslationCache:
    """In-memory cache backend (also the reference implementation)."""

    def __init__(self, *, target_lang: str = "ar", provider: str = DEFAULT_PROVIDER) -> None:
        self.target_lang = target_lang
        self.provider = provider
        self._store: dict[str, CacheRecord] = {}

    def key_for(self, entry: LocalizationEntry) -> str:
        return make_cache_key(entry, target_lang=self.target_lang, provider=self.provider)

    def lookup(self, entry: LocalizationEntry) -> CacheRecord | None:
        return self._store.get(self.key_for(entry))

    def remember(self, entry: LocalizationEntry, translated_text: str | None) -> CacheRecord:
        record = CacheRecord(
            key=self.key_for(entry),
            source_text=entry.source_text,
            translated_text=translated_text,
            target_lang=self.target_lang,
            provider=self.provider,
            engine=entry.engine,
        )
        self._store[record.key] = record
        return record

    def __len__(self) -> int:
        return len(self._store)
