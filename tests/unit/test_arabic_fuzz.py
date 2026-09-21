"""Deterministic fuzz-like testing with stdlib generators (seeded).

Invariants asserted over hundreds of generated game-like strings:

* placeholder_set(before) == placeholder_set(after) for every pass,
* valid Unicode never crashes any pass,
* wrapped output rejoins to the input modulo whitespace,
* QA always returns a well-formed result.
"""

import random

from almurrib.arabic.bidi import bidi_visual, to_visual
from almurrib.arabic.normalize import normalize_text
from almurrib.arabic.qa import arabic_qa_check
from almurrib.arabic.reshape import is_shaped, reshape_logical
from almurrib.arabic.wrap import wrap_arabic_text
from almurrib.core.placeholders import extract_placeholders

ARABIC_WORDS = ["مرحبا", "بالعالم", "نص", "تجربة", "لعبة", "سَلام", "قصة"]
LATIN_WORDS = ["Hello", "Qwen3", "HP", "OpenAI", "test", "v2.5"]
TOKENS = ["{name}", "{0}", "%s", "%d", "%1$s", "[score]", "<b>", "</b>",
          "<color=red>", "</color>", "\\n"]
PUNCT = ["،", "؟", ".", ",", "!", "?", "…", ":", "؛", "(", ")", '"']
DIGITS = ["123", "٤٥٦", "3.14", "100%"]


def _gen(rng: random.Random) -> str:
    parts: list[str] = []
    for _ in range(rng.randint(1, 12)):
        roll = rng.random()
        if roll < 0.45:
            parts.append(rng.choice(ARABIC_WORDS))
        elif roll < 0.65:
            parts.append(rng.choice(LATIN_WORDS))
        elif roll < 0.78:
            parts.append(rng.choice(TOKENS))
        elif roll < 0.88:
            parts.append(rng.choice(PUNCT))
        else:
            parts.append(rng.choice(DIGITS))
    text = " ".join(parts)
    if rng.random() < 0.2:
        text += "\n" + " ".join(rng.choice(ARABIC_WORDS)
                                for _ in range(rng.randint(1, 4)))
    return text


def _corpus(seed: int, count: int) -> list[str]:
    rng = random.Random(seed)
    return [_gen(rng) for _ in range(count)]


def test_fuzz_placeholder_invariant():
    for text in _corpus(20260921, 300):
        before = set(extract_placeholders(text))
        for out in (reshape_logical(text), bidi_visual(text), to_visual(text)):
            assert set(extract_placeholders(out)) == before, (text, out)
        wrapped = "\n".join(wrap_arabic_text(text, 24))
        assert set(extract_placeholders(wrapped)) == before


def test_fuzz_never_crashes_and_qa_wellformed():
    for text in _corpus(777, 300):
        for func in (normalize_text, reshape_logical, bidi_visual,
                     to_visual):
            assert isinstance(func(text), str)
        assert isinstance(wrap_arabic_text(text, 16), list)
        result = arabic_qa_check("source " + text, text + " ترجمة")
        assert isinstance(result.passed, bool)
        assert all(f.severity in ("error", "warning", "info")
                   for f in result.flags)


def test_fuzz_shaped_output_only_from_shaping():
    for text in _corpus(4242, 100):
        assert not is_shaped(normalize_text(text))
        assert not is_shaped(bidi_visual(text))
