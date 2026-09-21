"""Performance: glossary lookups, metric wrapping, repeated measurement."""

import time

from almurrib.arabic.wrap import wrap_arabic_text
from almurrib.core.glossary import Glossary, GlossaryEntry


def _glossary(size: int) -> Glossary:
    return Glossary([
        GlossaryEntry(source_term=f"Term{i:05d} Extra Words Here",
                      target_term=f"مصطلح{i}")
        for i in range(size)
    ] + [
        GlossaryEntry(source_term="Sylvie", target_term="سيلفي",
                      type="character"),
    ])


def _bench(name: str, func, count: int) -> float:
    start = time.perf_counter()
    for _ in range(count):
        func()
    elapsed = time.perf_counter() - start
    print(f"\nPERF {name}: {count} ops in {elapsed:.2f}s "
          f"({elapsed / count * 1000:.3f} ms/op)")
    return elapsed


def test_glossary_lookup_scales():
    text = ("Sylvie and Me discussed Term00042 Extra Words Here "
            "over a visual novel " * 4)
    for size in (100, 1000, 10000):
        glossary = _glossary(size)
        elapsed = _bench(f"glossary-lookup-{size}", lambda: glossary.lookup(text), 20)
        assert elapsed < 20.0
    assert len(_glossary(100).lookup(text)) >= 2


def test_metric_wrap_short_medium_long():
    from almurrib.arabic.fonts import FontMetrics
    from pathlib import Path

    font = Path(__file__).resolve().parents[2] / "fixtures" / "fonts" / \
        "Vazirmatn-Variable.ttf"
    import pytest

    if not font.exists():
        pytest.skip("bundled Vazirmatn fixture not present")
    metrics = FontMetrics(font, size=16)
    try:
        short = "مرحبا"
        medium = "مرحبا بالعالم الجميل " * 10
        long_text = "مرحبا بالعالم الجميل " * 200
        _bench("wrap-short", lambda: wrap_arabic_text(short, 200, metrics=metrics), 200)
        _bench("wrap-medium", lambda: wrap_arabic_text(medium, 200, metrics=metrics), 50)
        elapsed = _bench("wrap-long", lambda: wrap_arabic_text(
            long_text, 200, metrics=metrics), 5)
        assert elapsed < 20.0
        # repeated measurement benefits from the glyph cache
        first = _bench("measure-cold", lambda: metrics.width_of(medium), 1)
        second = _bench("measure-warm", lambda: metrics.width_of(medium), 50)
        assert second / 50 <= first + 0.01
    finally:
        metrics.close()
