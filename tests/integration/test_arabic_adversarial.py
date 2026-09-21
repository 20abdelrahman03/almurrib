"""Adversarial Arabic tests: deliberately trying to break the layer.

Covers PART 16/18: Unicode edges, punctuation, numbers, game syntax, long
text, mixed scripts, empty input, reprocessing, failure injection. Every
genuine bug found here got a fix + this regression.
"""

import pytest

from almurrib.arabic.bidi import bidi_visual, to_visual
from almurrib.arabic.masking import mask_protected, unmask_protected
from almurrib.arabic.normalize import contains_arabic, normalize_text
from almurrib.arabic.qa import arabic_qa_check
from almurrib.arabic.reshape import is_shaped, reshape_logical
from almurrib.arabic.wrap import wrap_arabic_text
from almurrib.core.placeholders import extract_placeholders


def _placeholders_intact(before: str, after: str) -> bool:
    return set(extract_placeholders(before)) == set(extract_placeholders(after))


# -- Unicode hostility ---------------------------------------------------------------

ADVERSARIAL = [
    "مَرحَباً بِالعَالَم",  # diacritics everywhere
    "نص\u0640ممدود",  # tatweel
    "س\u200dلام",  # ZWJ inside word
    "فار\u200cسی",  # ZWNJ
    "مرحبا\u200e test",  # explicit LRM
    "test\u200f مرحبا",  # explicit RLM
    "école مرحبا",  # NFD latin + arabic
    "مرحبا 😀🎮",  # emoji
    "日本語 مرحبا",  # Japanese + Arabic
    "中文 مرحبا",  # Chinese + Arabic
    "Привет مرحبا",  # Russian + Arabic
    "a" * 600,  # huge token, no spaces
    "!" * 200,  # huge punctuation run
    "   ",  # whitespace only
    "",  # empty
    "\n",  # newline only
    "\n\n\n",  # newline run
    "%s %d %1$s {0} {name} [v] <b>x</b> \\n \\t",  # token soup
    "{name}{name}{name}",  # repeated tokens
    "<color=red>نص <b>متداخل</b></color>",  # nested markup
    "نص 'باقتباس' \"مزدوج\" (بين قوسين) [بين معقوفتين]",
    "https://example.com/a?b=1 مرحبا user@x.com",
    "HP: 100 (50%) — v2.5 — 12:30 — 2026-09-21",
    "model qwen/qwen3-30b-a3b:free مرحبا",
    "خطأ \ud800 وحيد",  # lone surrogate halves
]


@pytest.mark.parametrize("text", ADVERSARIAL)
def test_processing_never_crashes(text):
    try:
        clean = text.encode("utf-8", "ignore").decode("utf-8")  # drop lone surrogates
    except Exception:
        clean = ""
    for func in (normalize_text, reshape_logical, bidi_visual, to_visual):
        out = func(clean)
        assert isinstance(out, str)
    assert isinstance(wrap_arabic_text(clean or "x", 20), list)
    assert isinstance(arabic_qa_check("src", clean or "x").flags, list)


@pytest.mark.parametrize("text", [t for t in ADVERSARIAL if t.strip() and "\ud800" not in t])
def test_placeholder_set_invariant(text):
    if not extract_placeholders(text):
        return
    for out in (reshape_logical(text), bidi_visual(text), to_visual(text)):
        assert _placeholders_intact(text, out), (text, out)
    for line in wrap_arabic_text(text, 12):
        pass  # wrap may relocate tokens across lines; union must hold
    assert _placeholders_intact(
        text, "\n".join(wrap_arabic_text(text, 12)))


def test_lri_pdi_rejected_by_bidi_engine_documented():
    """python-bidi 0.6.x raises on isolates: PUA masking exists because of this."""
    from bidi.algorithm import get_display

    with pytest.raises(AssertionError):
        get_display("a\u2066b\u2069")


def test_double_visual_documented_unstable_but_safe():
    once = to_visual("مرحبا {name} test")
    twice = to_visual(once)
    # Not equal (documented), but processing never crashes or loses tokens.
    assert _placeholders_intact(once, twice)


def test_masking_collision_and_overflow_guarded():
    with pytest.raises(ValueError):
        mask_protected("has \ue000 sentinel")
    many = " ".join("{v%d}" % i for i in range(7000))
    with pytest.raises(ValueError):
        mask_protected(many)


def test_qa_on_hostile_pairs_never_crashes():
    pairs = [
        ("", ""), ("x", ""), ("", "y"), ("A" * 2000, "ب" * 2000),
        ("Hi {broken", "مرحبا {broken"), ("<b>oops", "نص"),
        ("مرحبا", "مرحبا" * 500),
    ]
    for source, translation in pairs:
        result = arabic_qa_check(source, translation)
        assert isinstance(result.passed, bool)


def test_wrap_extremes():
    assert wrap_arabic_text("نص", 1) == ["ن", "ص"]
    assert wrap_arabic_text("", 10) == [""]
    long_token = "كلمة" * 200
    lines = wrap_arabic_text(f"قبل {long_token} بعد", 10)
    assert "".join(lines).replace(" ", "") == f"قبل{long_token}بعد".replace(" ", "")
    for bad in (0, -1, 3.5, "8", None):
        with pytest.raises(ValueError):
            wrap_arabic_text("نص", bad)  # type: ignore[arg-type]


def test_mixed_direction_sanity_spot_checks():
    # Pure Arabic + trailing Latin model id: tokens preserved, no crash.
    out = to_visual("تجربة Qwen3 الجديدة")
    assert "Qwen3" in out
    # Numbers embedded in Arabic reorder as a unit, digits intact.
    out = bidi_visual("عدد 125 نقطة")
    assert "125" in out
    # URL survives shaping pipeline untouched.
    out = to_visual("زر https://example.com هنا")
    assert "https://example.com" in out
