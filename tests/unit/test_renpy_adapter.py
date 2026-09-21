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
    assert len(entries) == 11

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


def test_packed_game_extracts_archived_scripts(tmp_path):
    """Loose .rpy plus a packed .rpa: both sources land with clear provenance."""
    from tests.conftest import build_test_rpa_v3

    game = tmp_path / "packed"
    (game / "game").mkdir(parents=True)
    (game / "game" / "script.rpy").write_text(
        'label start:\n    "Loose line."\n', encoding="utf-8")
    (game / "game" / "archive.rpa").write_bytes(build_test_rpa_v3({
        "packed.rpy": b'label start:\n    "Packed line."\n',
    }))
    entries = RenPyAdapter().extract(game)
    by_text = {e.source_text: e for e in entries}
    assert by_text["Loose line."].source_refs[0].file == "game/script.rpy"
    packed = by_text["Packed line."]
    assert packed.source_refs[0].file == "game/archive.rpa#packed.rpy"
    # detection still recognizes the packed game
    assert RenPyAdapter().detect(game).is_match


def test_corrupt_archive_does_not_kill_loose_extraction(tmp_path):
    game = tmp_path / "packed"
    (game / "game").mkdir(parents=True)
    (game / "game" / "script.rpy").write_text(
        'label start:\n    "Loose line."\n', encoding="utf-8")
    (game / "game" / "archive.rpa").write_bytes(b"RPA-3.0 " + b"0" * 60)
    entries = RenPyAdapter().extract(game)
    assert [e.source_text for e in entries] == ["Loose line."]


def test_extraction_is_deterministic(renpy_fixture_dir):
    first = entries_to_json(RenPyAdapter().extract(renpy_fixture_dir))
    second = entries_to_json(RenPyAdapter().extract(renpy_fixture_dir))
    assert first == second


def test_character_names_become_name_entries(tmp_path):
    from pathlib import Path

    game = tmp_path / "game_root"
    (game / "game").mkdir(parents=True)
    (game / "game" / "script.rpy").write_text(
        'define s = Character(_("Sylvie"))\n'
        "label start:\n"
        '    s "Hi."\n',
        encoding="utf-8",
    )
    entries = RenPyAdapter().extract(game)
    names = [e for e in entries if e.source_refs[0].statement == "name"]
    assert [(e.source_text, e.status.value) for e in names] == [
        ("Sylvie", "untranslated")]
    assert names[0].tags == ["character", "name"]
    assert names[0].speaker is None


def test_plain_names_emit_no_entry(tmp_path):
    from pathlib import Path

    game = tmp_path / "game_root"
    (game / "game").mkdir(parents=True)
    (game / "game" / "script.rpy").write_text(
        'define e = Character("Eileen")\n'
        "label start:\n"
        '    e "Hi."\n',
        encoding="utf-8",
    )
    entries = RenPyAdapter().extract(game)
    assert [e.source_text for e in entries] == ["Hi."]
    assert entries[0].speaker == "Eileen"  # still resolved for dialogue
