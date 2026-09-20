"""Ren'Py adapter tests against the deterministic fixture."""

from almurrib.core.model import EngineType, EntryStatus
from almurrib.engine_adapters.renpy import RenPyAdapter
from almurrib.engine_adapters.renpy.exporter import entries_to_json


def test_detect_fixture(renpy_fixture_dir):
    result = RenPyAdapter().detect(renpy_fixture_dir)
    assert result.is_match
    assert result.engine is EngineType.RENPY
    assert result.confidence >= 0.9


def test_detect_rejects_unrelated_dir(tmp_path):
    result = RenPyAdapter().detect(tmp_path)
    assert not result.is_match


def test_extract_fixture_entries(renpy_fixture_dir):
    entries = RenPyAdapter().extract(renpy_fixture_dir)
    assert len(entries) == 10

    by_text = {e.source_text: e for e in entries}

    # speakers resolved from Character() definitions
    assert by_text["Hello! Did you wait long?"].speaker == "Eileen"
    assert by_text["Not at all. I just arrived."].speaker == "Nadia"

    # narrator line has no speaker
    narrator = by_text["The wind blows over the empty street."]
    assert narrator.speaker is None
    assert "dialogue" in narrator.tags

    # menu choices tagged
    choice = by_text["Follow Eileen"]
    assert choice.source_refs[0].statement == "menu"
    assert "choice" in choice.tags

    # source references are precise enough for later reinjection
    hello = by_text["Hello! Did you wait long?"]
    assert hello.source_refs[0].file == "game/script.rpy"
    assert hello.source_refs[0].line == 9

    # existing translation pair
    pair = by_text["Tiny Fixture"]
    assert pair.translated_text == "اللعبة الصغيرة"
    assert pair.status is EntryStatus.TRANSLATED

    # everything else starts untranslated
    others = [e for e in entries if e.source_text != "Tiny Fixture"]
    assert all(e.status is EntryStatus.UNTRANSLATED for e in others)

    # options.rpy config strings must not leak in
    assert "Tiny Fixture" not in {
        e.source_text for e in others
    } or all(e.source_refs[0].file != "game/options.rpy" for e in entries)


def test_extraction_is_deterministic(renpy_fixture_dir):
    first = entries_to_json(RenPyAdapter().extract(renpy_fixture_dir))
    second = entries_to_json(RenPyAdapter().extract(renpy_fixture_dir))
    assert first == second
