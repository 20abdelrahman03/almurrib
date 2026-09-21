"""Glossary flow tests: context reaches prompts, QA flags, cache scoping."""

from almurrib.core.glossary import Glossary, GlossaryEntry
from almurrib.core.model import EngineType, EntryStatus, LocalizationEntry, SourceRef
from almurrib.core.provider import ProviderConfig
from almurrib.core.translate import RealTranslateStage
from almurrib.providers.fake import FakeProvider


def _entry(text: str, speaker: str | None = None) -> LocalizationEntry:
    ref = SourceRef(file="game/s.rpy", line=1)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY, source_text=text, speaker=speaker,
        context="file:game/s.rpy", source_refs=[ref])


class _Capture(FakeProvider):
    def __init__(self):
        super().__init__(ProviderConfig(
            provider="openai_compat", model="m",
            base_url="https://x", api_key="k"))
        self.seen = []

    def translate_batch(self, requests):
        self.seen.extend(requests)
        return super().translate_batch(requests)


def _glossary() -> Glossary:
    return Glossary([
        GlossaryEntry(source_term="Sylvie", target_term="سيلفي",
                      type="character", gender="female", style="colloquial"),
        GlossaryEntry(source_term="visual novel", target_term="رواية مرئية"),
    ])


def test_context_reaches_provider_request():
    provider = _Capture()
    stage = RealTranslateStage(provider, glossary=_glossary())
    stage.run([_entry("Hi Sylvie, read this visual novel", speaker="Me")],
              target_lang="ar")
    (request,) = provider.seen
    assert request.speaker_gender is None  # "Me" not in this glossary
    assert ("Sylvie", "سيلفي") in request.glossary_terms
    assert ("visual novel", "رواية مرئية") in request.glossary_terms


def test_speaker_gender_resolved():
    provider = _Capture()
    glossary = Glossary([GlossaryEntry(
        source_term="Me", target_term="أنا", type="character", gender="male")])
    RealTranslateStage(provider, glossary=glossary).run(
        [_entry("I agree", speaker="Me")], target_lang="ar")
    assert provider.seen[0].speaker_gender == "male"


def test_prompt_renders_glossary_and_traits():
    from almurrib.providers.prompts import build_messages
    from almurrib.core.provider import TranslationRequest

    messages = build_messages([TranslationRequest(
        entry_id="e1", source_text="Hi Sylvie", source_lang="en",
        target_lang="ar", speaker="Sylvie", speaker_gender="female",
        speaker_style="colloquial",
        glossary_terms=(("Sylvie", "سيلفي"),))])
    user_text = messages[1]["content"]
    assert "Sylvie (female, colloquial)" in user_text
    assert "glossary (use these translations): Sylvie -> سيلفي" in user_text


def test_glossary_mismatch_flagged_in_stage():
    class Arabic(FakeProvider):
        def translate_batch(self, requests):
            from almurrib.core.provider import TranslationResult

            return [TranslationResult(
                entry_id=r.entry_id, translated_text="أهلا نادية",
                provider="fake", model="m") for r in requests]

    stage = RealTranslateStage(Arabic(), glossary=_glossary())
    entry = _entry("Hi Sylvie")
    stats = stage.run([entry], target_lang="ar")
    assert entry.status is EntryStatus.FLAGGED
    assert any(f.startswith("glossary.mismatch:") for f in entry.qa_flags)
    assert stats.glossary_flags >= 1


def test_glossary_match_passes_quietly():
    class Good(FakeProvider):
        def translate_batch(self, requests):
            from almurrib.core.provider import TranslationResult

            return [TranslationResult(
                entry_id=r.entry_id, translated_text="أهلا سيلفي",
                provider="fake", model="m") for r in requests]

    stage = RealTranslateStage(Good(), glossary=_glossary())
    entry = _entry("Hi Sylvie")
    stats = stage.run([entry], target_lang="ar")
    assert entry.status is EntryStatus.TRANSLATED
    assert stats.glossary_flags == 0


def test_glossary_veto_invalidates_only_relevant_hits():
    """Edited glossaries retranslate precisely the violating entries."""
    from almurrib.core.cache import TranslationCache

    provider = FakeProvider()
    cache = TranslationCache(target_lang="ar", provider=provider.config.identity)
    glossary = Glossary([GlossaryEntry(source_term="Sylvie", target_term="سيلفي",
                                       type="character")])
    first = RealTranslateStage(provider, cache=cache, glossary=glossary)
    seeded = [_entry("Hi Sylvie"), _entry("Hello world")]
    stats1 = first.run(seeded, target_lang="ar")
    assert stats1.api_translated == 2

    # Glossary target changed: Sylvie line must retranslate, other line hits.
    glossary2 = Glossary([GlossaryEntry(source_term="Sylvie", target_term="XYZ",
                                        type="character")])
    second = RealTranslateStage(provider, cache=cache, glossary=glossary2)
    fresh = [_entry("Hi Sylvie"), _entry("Hello world")]
    stats2 = second.run(fresh, target_lang="ar")
    assert stats2.api_translated == 1
    assert stats2.cache_hits == 1
    assert fresh[0].translated_text == "<ar>Hi Sylvie</ar>"  # provider again
    assert fresh[1].translated_text == seeded[1].translated_text  # stable hit


def test_no_glossary_no_glossary_behavior():
    stage = RealTranslateStage(FakeProvider())
    entry = _entry("Hi Sylvie")
    stage.run([entry], target_lang="ar")
    assert all(not f.startswith("glossary.") for f in entry.qa_flags)
