"""Arabic processing unit tests (normalize / masking / reshape / bidi / wrap)."""

import pytest

from almurrib.arabic.bidi import bidi_visual, to_visual
from almurrib.arabic.masking import mask_protected, unmask_protected
from almurrib.arabic.normalize import contains_arabic, normalize_text
from almurrib.arabic.reshape import is_shaped, reshape_logical
from almurrib.arabic.wrap import CharMetrics, wrap_arabic_text


# -- normalization -------------------------------------------------------------

def test_nfc_composes_without_meaning_change():
    assert normalize_text("é") == "é"  # e + combining acute -> composed
    assert normalize_text("مرحبا") == "مرحبا"


def test_controls_dropped_tabs_newlines_kept():
    assert normalize_text("a\x00b\x1fc") == "abc"
    assert normalize_text("a\tb\nc") == "a\tb\nc"


def test_space_runs_collapse():
    assert normalize_text("a  b  c") == "a b c"


def test_diacritics_tatweel_digits_kept():
    text = "مَرحباً ـ ١٢٣"
    assert normalize_text(text) == text


def test_bad_form_rejected():
    with pytest.raises(ValueError):
        normalize_text("x", form="NOPE")


def test_contains_arabic():
    assert contains_arabic("مرحبا")
    assert not contains_arabic("Hello 123!")


# -- masking ---------------------------------------------------------------------

def test_mask_round_trip_order_safe():
    text = "[a] نص {name} <b>ت</b> %s"
    masked, table = mask_protected(text)
    assert extract_free(masked)
    assert unmask_protected(masked, table) == text


def extract_free(masked: str) -> bool:
    import re
    return not re.search(r"\{[A-Za-z_]\w*\}|\[[A-Za-z_][\w.]*\]|<[^>]*>|%[sd]", masked)


def test_mask_empty_when_no_tokens():
    masked, table = mask_protected("نص عادي")
    assert masked == "نص عادي" and table == {}
    assert unmask_protected(masked, table) == "نص عادي"


def test_unmask_rejects_unknown_sentinel():
    with pytest.raises(ValueError):
        unmask_protected(chr(0xE005), {chr(0xE001): "x"})


# -- reshaping ---------------------------------------------------------------------

def test_reshape_produces_presentation_forms():
    out = reshape_logical("مرحبا")
    assert is_shaped(out)
    assert out != "مرحبا"


def test_reshape_preserves_harakat():
    assert "َ" in reshape_logical("مَرحبا")  # fatha survives (not stripped)


def test_reshape_never_touches_placeholders():
    text = "{name} مرحبا [score] %s <b>نص</b>"
    out = reshape_logical(text)
    for token in ("{name}", "[score]", "%s", "<b>", "</b>"):
        assert token in out


def test_reshape_idempotent_and_guarded():
    once = reshape_logical("مرحبا بالعالم")
    assert reshape_logical(once) == once  # second pass is a no-op


def test_reshape_empty():
    assert reshape_logical("") == ""


# -- bidi ------------------------------------------------------------------------------

def test_bidi_keeps_tokens_atomic():
    out = bidi_visual("مرحبا {name}! HP: 100")
    assert "{name}" in out and "HP: 100" in out


def test_bidi_paragraphs_independent():
    two = "سطر أول\nsecond line here"
    assert bidi_visual(two).count("\n") == 1


def test_to_visual_combines_and_is_honest_about_idempotency():
    once = to_visual("مرحبا {name}")
    assert is_shaped(once)  # shaped output present
    # Visual-of-visual is NOT stable (documented): derive from logical only.
    assert to_visual(once) != once


def test_visual_restores_tokens_after_reorder():
    out = to_visual("[a] نص طويل هنا [b]")
    assert "[a]" in out and "[b]" in out


# -- wrapping -------------------------------------------------------------------------------

def test_wrap_basic_arabic():
    lines = wrap_arabic_text("مرحبا بالعالم الجميل", 10)
    assert lines == ["مرحبا", "بالعالم", "الجميل"]
    assert all(len(line) <= 10 for line in lines)


def test_wrap_keeps_tokens_atomic():
    # Protected token (13 wide) at width 5: own line, never split.
    assert wrap_arabic_text('xx {player_name} yy', 5) == \
        ['xx', '{player_name}', 'yy']


def test_wrap_paragraphs_never_merge():
    assert wrap_arabic_text("سطر أول\nسطر ثان", 100) == ["سطر أول", "سطر ثان"]


def test_wrap_long_word_breaks_and_marks():
    lines = wrap_arabic_text("abcdefghij", 4)
    assert lines == ["abcd", "efgh", "ij"]


def test_wrap_invalid_width_rejected():
    for bad in (0, -3, "10", None):
        with pytest.raises(ValueError):
            wrap_arabic_text("نص", bad)  # type: ignore[arg-type]


def test_custom_metrics_used():
    class Double(CharMetrics):
        def width_of(self, text: str) -> int:
            return 2 * len(text)

    assert wrap_arabic_text("ab cd", 5, metrics=Double()) == ["ab", "cd"]
