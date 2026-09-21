"""Translation stage tests (offline, fake provider)."""

from almurrib.core.cache import TranslationCache
from almurrib.core.model import EngineType, EntryStatus, LocalizationEntry, SourceRef
from almurrib.core.translate import RealTranslateStage
from almurrib.providers.fake import FakeProvider


def _entry(text: str, line: int, translated: str | None = None) -> LocalizationEntry:
    ref = SourceRef(file="game/script.rpy", line=line)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY,
        source_text=text,
        translated_text=translated,
        source_refs=[ref],
        status=EntryStatus.TRANSLATED if translated else EntryStatus.UNTRANSLATED,
    )


def test_translates_pending_entries_only():
    provider = FakeProvider()
    stage = RealTranslateStage(provider)
    entries = [_entry("A", 1), _entry("B", 2, translated="موجود مسبقًا")]
    stats = stage.run(entries, target_lang="ar")

    assert stats.already_translated == 1
    assert stats.api_translated == 1
    assert entries[0].translated_text == "<ar>A</ar>"
    # Fake output holds no Arabic script, so Arabic QA honestly flags it
    # (plumbing intact: text persisted, counted, exportable).
    assert entries[0].status is EntryStatus.FLAGGED
    assert any(f.startswith("no_arabic_script:") for f in entries[0].qa_flags)
    assert entries[1].translated_text == "موجود مسبقًا"  # untouched


def test_cache_hit_skips_api():
    provider = FakeProvider()
    cache = TranslationCache(target_lang="ar", provider=provider.config.identity)
    cached = _entry("Hello", 1)
    cache.remember(cached, "مرحبًا")

    stage = RealTranslateStage(provider, cache=cache)
    fresh = _entry("Hello", 1)
    stats = stage.run([fresh], target_lang="ar")

    assert stats.cache_hits == 1
    assert stats.api_translated == 0
    assert provider.calls == []  # no API call happened
    assert fresh.translated_text == "مرحبًا"


def test_cache_saved_after_api_call():
    provider = FakeProvider()
    cache = TranslationCache(target_lang="ar", provider=provider.config.identity)
    stage = RealTranslateStage(provider, cache=cache)
    entry = _entry("Hello", 1)
    stage.run([entry], target_lang="ar")
    assert cache.lookup(_entry("Hello", 1)).translated_text == "<ar>Hello</ar>"


def test_cache_stores_normalized_text_identical_to_entry():
    """Cache hits must serve exactly what entries carry (no NFC drift)."""

    class NfdProvider(FakeProvider):
        def translate_batch(self, requests):
            import unicodedata

            results = super().translate_batch(requests)
            for res in results:
                # é decomposed: NFD bytes differ from the NFC entry text.
                res.translated_text = unicodedata.normalize(
                    "NFD", "café مرحبا")
            return results

    import unicodedata

    from almurrib.arabic.normalize import normalize_text

    # Premise check: this string genuinely differs between NFC and NFD,
    # otherwise the test below would prove nothing.
    assert unicodedata.normalize("NFD", "café مرحبا").encode() != \
        unicodedata.normalize("NFC", "café مرحبا").encode()
    provider = NfdProvider()
    cache = TranslationCache(target_lang="ar", provider=provider.config.identity)
    stage = RealTranslateStage(provider, cache=cache)
    entry = _entry("Hello", 1)
    stage.run([entry], target_lang="ar")
    cached = cache.lookup(_entry("Hello", 1))
    assert cached is not None
    assert cached.translated_text == entry.translated_text
    assert cached.translated_text == normalize_text(cached.translated_text)


def test_translation_memory_reuse():
    provider = FakeProvider()
    memory_entry = _entry("Hello", 1)
    memory = {memory_entry.fingerprint: "مرحبًا"}
    stage = RealTranslateStage(provider, memory=memory)

    same_text_other_location = _entry("Hello", 99)
    stats = stage.run([same_text_other_location], target_lang="ar")

    assert stats.memory_hits == 1
    assert provider.calls == []
    assert same_text_other_location.translated_text == "مرحبًا"


def test_placeholder_failure_flags_entry():
    class BadProvider(FakeProvider):
        def translate_batch(self, requests):
            results = super().translate_batch(requests)
            for r in results:  # simulate model dropping the placeholder
                r.translated_text = r.translated_text.replace("{name}", "")
            return results

    stage = RealTranslateStage(BadProvider())
    entry = _entry("Hi {name}!", 1)
    stats = stage.run([entry], target_lang="ar")

    assert stats.placeholder_failures == 1
    assert entry.status is EntryStatus.FLAGGED
    assert any(f.startswith("placeholder_missing:") for f in entry.qa_flags)


def test_provider_failure_does_not_corrupt_entries():
    class FailingProvider(FakeProvider):
        def translate_batch(self, requests):
            raise RuntimeError("boom")

    stage = RealTranslateStage(FailingProvider())
    entry = _entry("Hello", 1)
    stats = stage.run([entry], target_lang="ar")

    assert stats.failed == 1
    assert entry.translated_text is None
    assert entry.status is EntryStatus.UNTRANSLATED


def test_batching_respects_batch_size():
    provider = FakeProvider()
    provider._config = provider.config.__class__(
        **{**provider.config.__dict__, "batch_size": 2}
    )
    stage = RealTranslateStage(provider)
    entries = [_entry(f"T{i}", i) for i in range(5)]
    stats = stage.run(entries, target_lang="ar")
    assert stats.api_calls == 3  # 2 + 2 + 1
    assert all(e.translated_text for e in entries)
