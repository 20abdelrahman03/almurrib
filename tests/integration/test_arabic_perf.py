"""Arabic layer performance measurements (actual numbers, generous bounds)."""

import time

from almurrib.arabic.bidi import to_visual
from almurrib.arabic.normalize import normalize_text
from almurrib.arabic.qa import arabic_qa_check
from almurrib.arabic.reshape import reshape_logical
from almurrib.arabic.wrap import wrap_arabic_text

SAMPLE = ("مرحبا {player_name}! هذه جملة اختبارية تحتوي على كلمات عديدة "
          "وأرقام 123 وعلامات، ونقاط. Qwen3 test. " * 3).strip()


def _bench(name: str, func, texts: list[str]) -> float:
    start = time.perf_counter()
    for text in texts:
        func(text)
    elapsed = time.perf_counter() - start
    print(f"\nPERF {name}: {len(texts)} texts in {elapsed:.2f}s "
          f"({elapsed / max(len(texts), 1) * 1000:.2f} ms/item)")
    return elapsed


def test_perf_scales():
    small = [SAMPLE] * 75
    medium = [SAMPLE] * 1000
    large = [SAMPLE] * 10000
    _bench("normalize-10k", normalize_text, large)
    _bench("reshape-1k", reshape_logical, medium)
    _bench("to_visual-1k", to_visual, medium)
    _bench("qa-1k", lambda t: arabic_qa_check("source " + t, t), medium)
    _bench("wrap-1k", lambda t: wrap_arabic_text(t, 40), medium)
    elapsed = _bench("to_visual-75", to_visual, small)
    assert elapsed < 30.0  # generous bound: game-sized batches stay interactive
