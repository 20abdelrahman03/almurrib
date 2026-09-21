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


def test_escaped_quotes_extract_runtime_values(tmp_path):
    """Regression: \"...\" must extract the runtime string, or Ren'Py
    string-translation lookup misses at display time (proven in production:
    two the_question lines stayed English)."""
    from almurrib.engine_adapters.renpy.parser import unescape_renpy_string

    assert unescape_renpy_string('So where does the \\"visual\\" part come in?') == \
        'So where does the "visual" part come in?'
    assert unescape_renpy_string('line\\nbreak\\ttab\\\\slash') == \
        'line\nbreak\ttab\\slash'
    assert unescape_renpy_string('caf\\u00e9') == 'café'
    assert unescape_renpy_string('keep \\qw') == 'keep \\qw'  # unknown: kept

    path = _write(
        tmp_path,
        "game/script.rpy",
        'label start:\n'
        '    s "So where does the \\"visual\\" part come in?"\n'
        '    "It\'s fine."\n'
        '    menu:\n'
        '        "Say \\"hi\\"" :\n'
        '            s "ok"\n',
    )
    statements = parse_rpy(path, game_root=tmp_path)
    by_text = {s.text: s.kind for s in statements}
    assert by_text['So where does the "visual" part come in?'] == "say"
    assert by_text["It's fine."] == "say"
    assert by_text['Say "hi"'] == "menu_choice"


def test_old_new_unescaped_to_runtime_values(tmp_path):
    path = _write(
        tmp_path,
        "game/tl/ar/strings.rpy",
        'translate ar strings:\n'
        '    old "a \\"b\\""\n'
        '    new "x"\n',
    )
    (statement,) = parse_rpy(path, game_root=tmp_path)
    assert statement.text == 'a "b"'
    assert statement.translation == "x"


def test_marked_character_name_extracted_plain_skipped(tmp_path):
    path = _write(
        tmp_path,
        "game/script.rpy",
        'define s = Character(_("Sylvie"), color="#c8ffc8")\n'
        'define e = Character("Eileen")\n'
        'label start:\n'
        '    s "Hi."\n',
    )
    statements = parse_rpy(path, game_root=tmp_path)
    names = [s for s in statements if s.kind == "character_name"]
    assert [(s.text, s.speaker_var) for s in names] == [("Sylvie", "s")]
    # plain (unmarked) names resolve speakers but emit no entry
    assert [s.text for s in statements if s.kind == "say"] == ["Hi."]
