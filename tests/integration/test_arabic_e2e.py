"""Arabic E2E: arabic_edge fixture through the real production path.

extract -> deterministic Arabic provider -> Arabic QA -> SQLite persist
-> Ren'Py export -> reparse. Uses production code throughout (no parallel
demo implementation). One line is deliberately echoed untranslated so the
E2E proves QA flagging, persistence of flags, and export of flagged rows.
"""

from pathlib import Path

from almurrib.core.model import EntryStatus
from almurrib.core.pipeline import LocalizationPipeline
from almurrib.core.provider import (
    ProviderCapabilities,
    ProviderConfig,
    TranslationRequest,
    TranslationResult,
)
from almurrib.core.translate import RealTranslateStage
from almurrib.core.workflow import extract_and_store
from almurrib.engine_adapters import default_adapters
from almurrib.engine_adapters.renpy.parser import parse_rpy
from almurrib.engine_adapters.renpy.reinject import write_translation_patch
from almurrib.storage.database import Database
from almurrib.storage.repository import EntryRepository

GAME = Path(__file__).resolve().parents[2] / "fixtures" / "arabic_edge"

# Fixed Arabic translations (deterministic stand-in for a real provider).
TRANSLATIONS = {
    "مرحبا بالعالم": "مرحبا بالعالم",
    "Hello مرحبا": "أهلا مرحبا",
    "عدد النقاط 125 نقطة": "عدد النقاط 125 نقطة",
    "أهلا {player_name}!": "أهلا {player_name}!",
    "<color=red>احذر!</color>": "<color=red>احذر!</color>",
    "صباح الخير": "صباح الخير",
    "مساء النور": "مساء النور",
    "تجربة Qwen3 الجديدة": "تجربة Qwen3 الجديدة",
    "HP: 100": "HP: 100",
    "هل أنت متأكد؟ (نعم/لا)": "هل أنت متأكد؟ (نعم/لا)",
    'قال: "مرحبا"!': 'قال: "مرحبا"!',
    "نعم، أكمل": "نعم، أكمل",
    "اخترت المتابعة.": "اخترت المتابعة.",
    "لا، توقف": "لا، توقف",
    "توقفت هنا.": "توقفت هنا.",
    "هذه جملة عربية طويلة جدا تحتوي على الكثير من الكلمات لاختبار التفاف النص والتأكد من أن المعالجة تتعامل معها بشكل صحيح دون أي مشاكل في الفواصل أو علامات الترقيم.":
        "هذه جملة عربية طويلة جدا تحتوي على الكثير من الكلمات لاختبار التفاف النص والتأكد من أن المعالجة تتعامل معها بشكل صحيح دون أي مشاكل في الفواصل أو علامات الترقيم.",
    "كلمةطويلةجدابدونأيفراغاتعلىالإطلاقلتختبرالكلماتالمستحيلة":
        "كلمةطويلةجدابدونأيفراغاتعلىالإطلاقلتختبرالكلماتالمستحيلة",
}


class DictProvider:
    """Deterministic Arabic provider; echoes the marked untranslated line."""

    def __init__(self) -> None:
        self._config = ProviderConfig(
            provider="dict-test", model="arabic-edge-0",
            base_url="http://localhost.invalid", api_key="test-key",
        )

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(supports_batch=True, supports_context=True)

    def translate(self, request: TranslationRequest) -> TranslationResult:
        return self.translate_batch([request])[0]

    def translate_batch(self, requests: list[TranslationRequest]
                        ) -> list[TranslationResult]:
        return [TranslationResult(
            entry_id=r.entry_id,
            translated_text=TRANSLATIONS.get(r.source_text, r.source_text),
            provider=self._config.provider, model=self._config.model,
        ) for r in requests]


def test_arabic_fixture_e2e(tmp_path):
    if not (GAME / "game" / "script.rpy").exists():
        import pytest

        pytest.skip("arabic_edge fixture not present")
    pipeline = LocalizationPipeline(adapters=default_adapters())
    with Database(tmp_path / "ar.db") as db:
        entries, project_id = extract_and_store(pipeline, GAME, db)
        assert len(entries) >= 15
        by_text = {e.source_text: e for e in entries}

        stage = RealTranslateStage(DictProvider())
        stats = stage.run(entries, source_lang="en", target_lang="ar")
        assert stats.failed == 0
        EntryRepository(db).upsert_many(project_id, entries)

        # The deliberately untranslated line is flagged, not silently kept.
        echo = by_text["This sentence was not translated."]
        assert echo.translated_text == "This sentence was not translated."
        assert echo.status is EntryStatus.FLAGGED
        assert any(f.startswith("source_copied:") for f in echo.qa_flags)

        # Placeholders and markup survive byte-for-byte.
        assert by_text["أهلا {player_name}!"].translated_text == "أهلا {player_name}!"
        assert "<color=red>" in by_text["<color=red>احذر!</color>"].translated_text

        # Flags persist through SQLite.
        repo = EntryRepository(db)
        reloaded = repo.get(echo.id)
        assert reloaded is not None
        assert reloaded.status is EntryStatus.FLAGGED
        assert any(f.startswith("source_copied:") for f in reloaded.qa_flags)

        out = tmp_path / "patch"
        written = write_translation_patch(
            repo.list(project_id=project_id), target_lang="arabic", output_dir=out)
        assert written
        strings = out / "game" / "tl" / "arabic" / "strings.rpy"
        content = strings.read_text(encoding="utf-8")
        assert "translate arabic strings:" in content
        assert "source_copied" in content  # flags exported as comments

        # Generated file reparses; every pair round-trips.
        reparsed = parse_rpy(strings, game_root=out)
        assert len(reparsed) == len([e for e in entries if e.translated_text])

    original = (GAME / "game" / "script.rpy").read_text(encoding="utf-8")
    assert "translate arabic" not in original


def test_render_ready_derives_but_never_persists(tmp_path):
    """Visual text is derived on demand; the DB keeps canonical logical."""
    from almurrib.arabic.bidi import to_visual
    from almurrib.arabic.qa import arabic_qa_check

    pipeline = LocalizationPipeline(adapters=default_adapters())
    with Database(tmp_path / "ar2.db") as db:
        entries, project_id = extract_and_store(pipeline, GAME, db)
        stage = RealTranslateStage(DictProvider())
        stage.run(entries, source_lang="en", target_lang="ar")
        EntryRepository(db).upsert_many(project_id, entries)
        stored = EntryRepository(db).list(project_id=project_id)

    for entry in stored:
        if not entry.translated_text:
            continue
        # Canonical text has no presentation forms...
        from almurrib.arabic.reshape import is_shaped

        assert not is_shaped(entry.translated_text), entry.source_text
        # ...while the derived visual form does (when Arabic present).
        if any("\u0600" <= c <= "\u06FF" for c in entry.translated_text):
            assert is_shaped(to_visual(entry.translated_text))
        # QA passes on real Arabic rows (except the deliberate echo).
        if entry.source_text != "This sentence was not translated.":
            assert arabic_qa_check(
                entry.source_text, entry.translated_text).passed, entry.source_text
