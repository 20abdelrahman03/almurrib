"""Real Ren'Py game validation: Ren'Py's official demo "The Question".

The script is part of the Ren'Py engine distribution (MIT-licensed,
github.com/renpy/renpy under the_question/). Only the script source is
vendored for tests — no assets, no redistribution beyond the source file.

Validates: detect → extract (speakers, menus) → translate (fake) → export
→ well-formed Ren'Py translation files → original untouched.
"""

from pathlib import Path

import pytest

from almurrib.core.pipeline import LocalizationPipeline, PipelineContext
from almurrib.core.translate import RealTranslateStage
from almurrib.core.workflow import extract_and_store
from almurrib.engine_adapters import default_adapters
from almurrib.engine_adapters.renpy.parser import parse_rpy
from almurrib.engine_adapters.renpy.reinject import write_translation_patch
from almurrib.providers.fake import FakeProvider
from almurrib.storage.database import Database

GAME = Path(__file__).resolve().parents[2] / "fixtures" / "the_question"


@pytest.fixture(scope="module")
def game_dir() -> Path:
    if not (GAME / "game" / "script.rpy").exists():
        pytest.skip("the_question fixture not present")
    return GAME


def test_real_game_detect_and_extract(game_dir):
    pipeline = LocalizationPipeline(adapters=default_adapters())
    adapter = pipeline.detect_engine(game_dir)
    assert adapter.engine_type.value == "renpy"

    entries = adapter.extract(game_dir)
    assert len(entries) >= 70
    speakers = {e.speaker for e in entries if e.speaker}
    assert {"Sylvie", "Me"} <= speakers
    menus = [e for e in entries if e.source_refs[0].statement == "menu"]
    assert len(menus) == 4


def test_real_game_full_localization_round_trip(game_dir, tmp_path):
    pipeline = LocalizationPipeline(adapters=default_adapters())
    with Database(tmp_path / "q.db") as db:
        entries, _ = extract_and_store(pipeline, game_dir, db)
        stage = RealTranslateStage(FakeProvider())
        untranslated = [e for e in entries if not e.translated_text]
        stats = stage.run(untranslated, source_lang="en", target_lang="ar")
        assert stats.failed == 0
        assert stats.api_translated == len(untranslated)

        out_dir = tmp_path / "patch"
        written = write_translation_patch(entries, target_lang="arabic", output_dir=out_dir)

    assert written
    tl_strings = out_dir / "game" / "tl" / "arabic" / "strings.rpy"
    assert tl_strings.exists()

    content = tl_strings.read_text(encoding="utf-8")
    assert "translate arabic strings:" in content
    assert 'old "Hi there! How was class?"' in content
    # menu choices present as pairs
    assert 'old "To ask her right away."' in content

    # generated translation file is itself parseable by our parser:
    # every old/new pair round-trips through the extraction layer
    reparsed = parse_rpy(tl_strings, game_root=out_dir)
    assert len(reparsed) == len(entries)
    assert all(s.translation and s.translation.startswith("<ar>") for s in reparsed)

    # original game script untouched
    original = (game_dir / "game" / "script.rpy").read_text(encoding="utf-8")
    assert "translate arabic" not in original
    assert "<ar>" not in original
