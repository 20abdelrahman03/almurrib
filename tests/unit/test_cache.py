"""Cache tests: in-memory and SQLite backends share key semantics."""

from almurrib.core.cache import DEFAULT_PROVIDER, TranslationCache, make_cache_key
from almurrib.core.model import EngineType, LocalizationEntry, SourceRef
from almurrib.storage.cache import SQLiteCache
from almurrib.storage.database import Database


def _entry(text: str = "Hello!") -> LocalizationEntry:
    ref = SourceRef(file="game/script.rpy", line=9)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY,
        source_text=text,
        speaker="Eileen",
        context="speaker:Eileen",
        source_refs=[ref],
    )


def test_cache_key_is_deterministic():
    entry = _entry()
    assert make_cache_key(entry, target_lang="ar") == make_cache_key(entry, target_lang="ar")
    assert make_cache_key(entry, target_lang="ar") != make_cache_key(entry, target_lang="fr")
    assert make_cache_key(entry, target_lang="ar", provider="qwen2.5-7b") != make_cache_key(
        entry, target_lang="ar", provider=DEFAULT_PROVIDER
    )


def test_in_memory_cache_round_trip():
    cache = TranslationCache(target_lang="ar")
    entry = _entry()
    assert cache.lookup(entry) is None
    cache.remember(entry, "مرحباً!")
    record = cache.lookup(entry)
    assert record is not None
    assert record.translated_text == "مرحباً!"
    assert len(cache) == 1


def test_sqlite_cache_round_trip(tmp_path):
    with Database(tmp_path / "cache.db") as db:
        cache = SQLiteCache(db, target_lang="ar")
        entry = _entry()
        assert cache.lookup(entry) is None
        cache.remember(entry, "مرحباً!")
        record = cache.lookup(entry)
        assert record is not None
        assert record.translated_text == "مرحباً!"
        assert len(cache) == 1

    # persistence: a fresh connection sees the same record
    with Database(tmp_path / "cache.db") as db2:
        cache2 = SQLiteCache(db2, target_lang="ar")
        assert cache2.lookup(_entry()) is not None


def test_cache_distinguishes_context():
    cache = TranslationCache(target_lang="ar")
    a = _entry()
    b = _entry()
    b.context = "speaker:SomeoneElse"
    cache.remember(a, "مرحباً!")
    assert cache.lookup(a) is not None
    assert cache.lookup(b) is None
