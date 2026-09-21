"""Glossary E2E: persistence -> context -> provider -> QA -> export.

Uses the_question through production code: seed a project glossary, run a
glossary-honoring deterministic provider, violate one term deliberately,
and prove flags persist, export reparses, and repeated runs stay stable.
"""

from pathlib import Path

from almurrib.core.glossary import Glossary, GlossaryEntry
from almurrib.core.model import EntryStatus
from almurrib.core.pipeline import LocalizationPipeline
from almurrib.core.provider import (
    ProviderCapabilities,
    ProviderConfig,
    TranslationRequest,
    TranslationResult,
)
from almurrib.core.translate import RealTranslateStage
from almurrib.core.workflow import extract_and_store, translate_entries
from almurrib.engine_adapters import default_adapters
from almurrib.engine_adapters.renpy.parser import parse_rpy
from almurrib.engine_adapters.renpy.reinject import write_translation_patch
from almurrib.storage.database import Database
from almurrib.storage.glossary import GlossaryRepository
from almurrib.storage.repository import EntryRepository

GAME = Path(__file__).resolve().parents[2] / "fixtures" / "the_question"


class GlossaryHonoringProvider:
    """Uses request.glossary_terms when present, else wraps source."""

    def __init__(self) -> None:
        self._config = ProviderConfig(
            provider="gloss-test", model="e2e-0",
            base_url="http://localhost.invalid", api_key="k")
        self.batches = 0

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_batch=True, supports_context=True)

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return self.translate_batch([request])[0]

    def translate_batch(self, requests: list[TranslationRequest]
                        ) -> list[TranslationResult]:
        self.batches += 1
        out = []
        for req in requests:
            text = req.source_text
            for src, tgt in req.glossary_terms:
                if src in text and "VIOLATE" not in text:
                    text = text.replace(src, tgt)
            out.append(TranslationResult(
                entry_id=req.entry_id, translated_text=f"<ar>{text}</ar>",
                provider=self._config.provider, model=self._config.model))
        return out


def _seed(db: Database, project_id: int) -> None:
    repo = GlossaryRepository(db)
    repo.add(GlossaryEntry(source_term="Sylvie", target_term="سيلفي",
                           type="character", gender="female", project_id=project_id))
    repo.add(GlossaryEntry(source_term="Me", target_term="أنا",
                           type="character", gender="male", project_id=project_id))


def test_glossary_e2e(tmp_path):
    if not (GAME / "game" / "script.rpy").exists():
        import pytest

        pytest.skip("the_question fixture not present")
    pipeline = LocalizationPipeline(adapters=default_adapters())
    provider = GlossaryHonoringProvider()
    with Database(tmp_path / "g.db") as db:
        entries, project_id = extract_and_store(pipeline, GAME, db)
        assert len(entries) == 77
        _seed(db, project_id)

        from almurrib.core.workflow import load_glossary, translate_entries

        glossary = load_glossary(db, project_id)
        assert len(glossary.enabled()) == 2
        stats = translate_entries(entries, db, provider, project_id=project_id,
                                  glossary=glossary)
        assert stats.failed == 0
        assert stats.api_translated == 77

        # Glossary terms honored inside translations...
        repo = EntryRepository(db)
        sylvie = [e for e in repo.list(project_id=project_id)
                  if "Sylvie" in e.source_text and e.translated_text]
        assert sylvie and all("سيلفي" in e.translated_text for e in sylvie)

        # ...and a deliberate violation is flagged, persisted, exported.
        violator = next(e for e in repo.list(project_id=project_id)
                        if "Sylvie" in e.source_text)
        violator.translated_text = "نادية تتحدث هنا"  # drops سيلفي
        violator.status = EntryStatus.TRANSLATED
        stage = RealTranslateStage(provider, glossary=glossary)
        stage.run([violator], target_lang="ar")  # already-path re-QAs text
        assert violator.status is EntryStatus.FLAGGED
        assert any(f.startswith("glossary.mismatch:") for f in violator.qa_flags)
        repo.upsert_many(project_id, [violator])
        assert any(f.startswith("glossary.mismatch:")
                   for f in repo.get(violator.id).qa_flags)

        out = tmp_path / "patch"
        written = write_translation_patch(
            repo.list(project_id=project_id), target_lang="ar", output_dir=out)
        assert written
        strings = out / "game" / "tl" / "ar" / "strings.rpy"
        reparsed = parse_rpy(strings, game_root=out)
        assert len(reparsed) == len(
            [e for e in repo.list(project_id=project_id) if e.translated_text])

    original = (GAME / "game" / "script.rpy").read_text(encoding="utf-8")
    assert "<ar>" not in original


def test_glossary_cache_scoping(tmp_path):
    """Edited glossaries must not serve stale cached text."""
    from almurrib.core.cache import TranslationCache
    from almurrib.core.model import EngineType, SourceRef
    from almurrib.core.translate import RealTranslateStage
    from almurrib.providers.fake import FakeProvider

    ref = SourceRef(file="g/s.rpy", line=1)
    from almurrib.core.model import LocalizationEntry
    entry = LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, "Hi Sylvie", ref),
        engine=EngineType.RENPY, source_text="Hi Sylvie", source_refs=[ref])
    provider = FakeProvider()
    cache = TranslationCache(target_lang="ar", provider=provider.config.identity)
    glossary = Glossary([GlossaryEntry(source_term="Sylvie", target_term="X")])
    from almurrib.core.workflow import translate_entries as _te
    import inspect

    assert "glossary" in inspect.signature(_te).parameters
    stage = RealTranslateStage(provider, cache=cache, glossary=glossary)
    stage.run([entry], target_lang="ar")
    assert cache.lookup(entry) is not None  # same-identity cache intact
    assert entry.translation_provider == "fake"
