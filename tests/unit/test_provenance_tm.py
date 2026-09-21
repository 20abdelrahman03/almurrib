"""Provenance + TM gating + force semantics tests (offline)."""

from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
    TranslationSource,
)
from almurrib.core.translate import RealTranslateStage, TMRecord, tm_reusable
from almurrib.providers.fake import FakeProvider


def _entry(text: str = "Hello", line: int = 1, **kw) -> LocalizationEntry:
    ref = SourceRef(file="game/s.rpy", line=line)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY,
        source_text=text,
        source_refs=[ref],
        **kw,
    )


def _machine(provider: str | None, model: str | None = "m") -> TMRecord:
    return TMRecord(text="T", source="machine", provider=provider, model=model)


def test_human_and_imported_tm_always_reusable():
    for source in ("human", "imported"):
        rec = TMRecord(text="T", source=source)
        assert tm_reusable(rec, current_identity="a:x", allow_cross_model_machine=False)


def test_machine_tm_gated_by_identity():
    same = _machine("openai_compat:m")
    other = _machine("openai_compat:other")
    assert tm_reusable(same, current_identity="openai_compat:m",
                       allow_cross_model_machine=False)
    assert not tm_reusable(other, current_identity="openai_compat:m",
                           allow_cross_model_machine=False)
    assert tm_reusable(other, current_identity="openai_compat:m",
                       allow_cross_model_machine=True)


def test_legacy_machine_tm_without_provider_reusable():
    assert tm_reusable(_machine(None), current_identity="a:x",
                       allow_cross_model_machine=False)


def test_unknown_sources_never_reused():
    assert not tm_reusable(TMRecord(text="T", source="memory"),
                           current_identity="a:x", allow_cross_model_machine=True)


def test_cross_model_machine_tm_not_silent_by_default():
    provider = FakeProvider()
    identity = provider.config.identity
    memory = { _entry().fingerprint: _machine("other:model") }
    stage = RealTranslateStage(provider, memory=memory)
    entry = _entry()
    stats = stage.run([entry], target_lang="ar")
    assert stats.memory_hits == 0
    assert stats.api_translated == 1  # went to the provider instead


def test_same_model_machine_tm_reused():
    provider = FakeProvider()
    memory = {_entry().fingerprint: _machine(provider.config.identity)}
    stage = RealTranslateStage(provider, memory=memory)
    stats = stage.run([_entry()], target_lang="ar")
    assert stats.memory_hits == 1


def test_force_skips_tm_cache_and_translated():
    provider = FakeProvider()
    cache_entries = [_entry("Cached", 5)]
    from almurrib.core.cache import TranslationCache
    cache = TranslationCache(target_lang="ar", provider=provider.config.identity)
    cache.remember(cache_entries[0], "old-cached")
    memory = {_entry("Mem", 6).fingerprint: _machine(provider.config.identity)}
    translated = _entry("Done", 7, translated_text="old-done",
                        status=EntryStatus.TRANSLATED)
    batch = [_entry("Cached", 5), _entry("Mem", 6), translated]
    stage = RealTranslateStage(provider, cache=cache, memory=memory, force=True)
    stats = stage.run(batch, target_lang="ar")
    assert stats.memory_hits == 0
    assert stats.cache_hits == 0
    assert stats.already_translated == 0
    assert stats.api_translated == 3
    assert all(e.translation_source == TranslationSource.MACHINE.value for e in batch)


def test_api_results_carry_provenance():
    provider = FakeProvider()
    stage = RealTranslateStage(provider)
    (entry,) = [_entry()]
    stage.run([entry], target_lang="ar")
    assert entry.translation_provider == provider.config.provider
    assert entry.translation_model == provider.config.model
    assert entry.translation_source == TranslationSource.MACHINE.value


def test_broken_translation_not_cached():
    class Bad(FakeProvider):
        def translate_batch(self, requests):
            results = super().translate_batch(requests)
            for r in results:
                r.translated_text = "no tokens here"
            return results

    from almurrib.core.cache import TranslationCache
    cache = TranslationCache(target_lang="ar", provider="fake:deterministic-0")
    stage = RealTranslateStage(Bad(), cache=cache)
    stage.run([_entry("Hi {name}!", 1)], target_lang="ar")
    # Same text via a good provider must NOT hit the broken cached value.
    assert cache.lookup(_entry("Hi {name}!", 1)) is None


def test_missing_ids_counted_as_failed():
    class Partial(FakeProvider):
        def translate_batch(self, requests):
            return super().translate_batch(requests[:1])

    stage = RealTranslateStage(Partial())
    stats = stage.run([_entry("A", 1), _entry("B", 2)], target_lang="ar")
    assert stats.api_translated == 1
    assert stats.failed == 1
    assert stats.errors


def test_obsolete_entries_excluded():
    stage = RealTranslateStage(FakeProvider())
    gone = _entry("Gone", 9, status=EntryStatus.OBSOLETE)
    stats = stage.run([gone, _entry("Live", 10)], target_lang="ar")
    assert stats.total == 1
    assert stats.api_translated == 1
    assert gone.translated_text is None
