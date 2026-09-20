"""Placeholder protection tests."""

from almurrib.core.placeholders import extract_placeholders, validate_translation


def test_extract_common_tokens():
    text = "Hello {player_name}, you have %d coins and {0} lives. [points] <color=red>HP</color>\\nNext"
    tokens = extract_placeholders(text)
    assert "{player_name}" in tokens
    assert "%d" in tokens
    assert "{0}" in tokens
    assert "[points]" in tokens
    assert "<color=red>" in tokens
    assert "</color>" in tokens
    assert "\\n" in tokens


def test_no_tokens_in_plain_text():
    assert extract_placeholders("Just a plain sentence.") == []


def test_validate_ok_when_all_tokens_preserved():
    src = "Welcome {name}! You won %d points."
    tgt = "مرحبًا {name}! لقد ربحت %d نقطة."
    report = validate_translation(src, tgt)
    assert report.ok
    assert report.missing == []


def test_validate_flags_missing_tokens():
    src = "Welcome {name}! You won %d points."
    tgt = "مرحبًا! لقد ربحت نقاطًا."  # dropped {name} and %d
    report = validate_translation(src, tgt)
    assert not report.ok
    assert "{name}" in report.missing
    assert "%d" in report.missing


def test_validate_catches_translated_identifier():
    src = "Score: [score]"
    tgt = "النتيجة: [النتيجة]"  # model "translated" the variable name
    report = validate_translation(src, tgt)
    assert not report.ok
    assert "[score]" in report.missing
