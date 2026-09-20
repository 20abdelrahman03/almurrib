"""Ren'Py parser unit tests."""

from pathlib import Path

import pytest

from almurrib.core.errors import ExtractionError
from almurrib.engine_adapters.renpy.parser import parse_rpy


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_say_statements_with_and_without_speaker(tmp_path):
    path = _write(
        tmp_path,
        "game/script.rpy",
        'define e = Character("Eileen")\n'
        '\n'
        'label start:\n'
        '    "Narrator line."\n'
        '    e "Hello there."\n',
    )
    statements = parse_rpy(path, game_root=tmp_path)
    assert [s.kind for s in statements] == ["say", "say"]
    assert statements[0].speaker is None
    assert statements[0].text == "Narrator line."
    assert statements[1].speaker == "Eileen"
    assert statements[1].speaker_var == "e"
    assert statements[1].text == "Hello there."
    assert statements[1].line == 5


def test_menu_choices_extracted(tmp_path):
    path = _write(
        tmp_path,
        "game/script.rpy",
        'label start:\n'
        '    menu:\n'
        '        "Go left":\n'
        '            e "Left it is."\n'
        '        "Go right":\n'
        '            e "Right."\n',
    )
    statements = parse_rpy(path, game_root=tmp_path)
    kinds = [s.kind for s in statements]
    assert kinds == ["menu_choice", "say", "menu_choice", "say"]
    assert statements[0].text == "Go left"
    assert statements[2].text == "Go right"


def test_translate_strings_pairs_extracted_with_translation(tmp_path):
    path = _write(
        tmp_path,
        "game/tl/arabic/strings.rpy",
        'translate arabic strings:\n'
        '    old "Hello"\n'
        '    new "مرحباً"\n',
    )
    statements = parse_rpy(path, game_root=tmp_path)
    assert len(statements) == 1
    s = statements[0]
    assert s.kind == "translated_string"
    assert s.text == "Hello"
    assert s.translation == "مرحباً"


def test_code_and_comments_are_ignored(tmp_path):
    path = _write(
        tmp_path,
        "game/script.rpy",
        '# a comment with "quotes"\n'
        'define config.name = "ShouldNotAppear"\n'
        'image bg = "bg.png"\n'
        'init python:\n'
        '    x = "not dialogue"\n'
        'label start:\n'
        '    jump end\n'
        'label end:\n'
        '    "Real dialogue."\n',
    )
    statements = parse_rpy(path, game_root=tmp_path)
    assert [s.text for s in statements] == ["Real dialogue."]


def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(ExtractionError) as exc_info:
        parse_rpy(tmp_path / "game" / "nope.rpy", game_root=tmp_path)
    assert "extract" in str(exc_info.value)
