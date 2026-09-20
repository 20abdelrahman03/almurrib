"""Round-trip test: fixture → extract → translate (fake) → export → inspect.

Fully offline: uses the deterministic FakeProvider. Proves the whole
pipeline shape works end to end without any external API.
"""

from almurrib.core.model import EntryStatus
from almurrib.core.pipeline import LocalizationPipeline, PipelineContext
from almurrib.core.translate import RealTranslateStage
from almurrib.core.workflow import extract_and_store
from almurrib.engine_adapters import default_adapters
from almurrib.engine_adapters.renpy.reinject import write_translation_patch
from almurrib.providers.fake import FakeProvider
from almurrib.storage.database import Database


def test_fixture_round_trip(renpy_fixture_dir, tmp_path):
    db_path = tmp_path / "rt.db"
    pipeline = LocalizationPipeline(adapters=default_adapters())

    with Database(db_path) as db:
        entries, _ = extract_and_store(pipeline, renpy_fixture_dir, db)
        assert len(entries) == 11

        # translate the untranslated ones with the fake provider
        stage = RealTranslateStage(FakeProvider())
        untranslated = [e for e in entries if not e.translated_text]
        stats = stage.run(untranslated, source_lang="en", target_lang="ar")
        assert stats.api_translated == 10
        assert stats.placeholder_failures == 0
        all_entries = entries  # mutate in place; untranslated were updated

        out_dir = tmp_path / "patch"
        written = write_translation_patch(all_entries, target_lang="arabic", output_dir=out_dir)

    assert written
    strings_tl = out_dir / "game" / "tl" / "arabic" / "strings.rpy"
    assert strings_tl.exists()

    strings_content = strings_tl.read_text(encoding="utf-8")
    assert "translate arabic strings:" in strings_content
    # dialogue became string pairs
    assert 'old "Hello! Did you wait long?"' in strings_content
    assert 'new "<ar>Hello! Did you wait long?</ar>"' in strings_content
    # menu choices too
    assert 'old "Follow Eileen"' in strings_content
    assert 'new "<ar>Follow Eileen</ar>"' in strings_content
    # the fixture's own pre-translated pair is carried through
    assert "اللعبة الصغيرة" in strings_content
    # placeholders survive the whole round trip
    assert "[score]" in strings_content
    assert "{player_name}" in strings_content

    # original fixture untouched
    original = (renpy_fixture_dir / "game" / "script.rpy").read_text(encoding="utf-8")
    assert "translate arabic" not in original
