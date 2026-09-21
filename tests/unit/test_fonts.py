"""Font foundation tests (metadata, discovery, manifest, metrics)."""

import pytest

from almurrib.arabic.fonts import FontAsset, FontMetrics, FontRegistry
from almurrib.arabic.wrap import wrap_arabic_text


def test_asset_defaults_license_unknown(tmp_path):
    asset = FontAsset(name="X", path=tmp_path / "x.ttf", format="ttf")
    assert asset.license == "Unknown"
    assert not asset.exists()
    d = asset.to_dict()
    assert d["name"] == "X" and d["format"] == "ttf"


def test_scan_registers_font_files_only(tmp_path):
    (tmp_path / "a.ttf").write_bytes(b"fake")
    (tmp_path / "b.otf").write_bytes(b"fake")
    (tmp_path / "notes.txt").write_text("nope")
    registry = FontRegistry()
    found = registry.scan(tmp_path)
    assert len(found) == 2
    assert len(registry) == 2
    assert {a.format for a in found} == {"ttf", "otf"}
    manifest = registry.manifest()
    assert manifest["format"] == "almurrib-fonts"
    assert len(manifest["fonts"]) == 2


def test_list_filters_family():
    registry = FontRegistry()
    from pathlib import Path

    registry.register(FontAsset(name="A", path=Path("a.ttf"), format="ttf",
                                family="Vazirmatn"))
    registry.register(FontAsset(name="B", path=Path("b.ttf"), format="ttf",
                                family="Cairo"))
    assert [a.name for a in registry.list(family="vazirmatn")] == ["A"]
    assert len(registry.list()) == 2


def _vazirmatn() -> FontMetrics:
    from pathlib import Path

    font = Path(__file__).resolve().parents[2] / "fixtures" / "fonts" / \
        "Vazirmatn-Variable.ttf"
    if not font.exists():
        pytest.skip("bundled Vazirmatn fixture not present")
    return FontMetrics(font, size=16)


def test_metrics_measure_and_coverage():
    metrics = _vazirmatn()
    try:
        assert metrics.has_glyph("م")
        assert not metrics.has_glyph("😀")
        arabic = metrics.width_of("مرحبا")
        latin = metrics.width_of("Hello")
        assert arabic > latin > 0  # real advances, not char counts
        assert metrics.line_height() > metrics.size // 2
        assert metrics.glyph_width("?") > 0  # missing -> fallback, never 0
    finally:
        metrics.close()


def test_metrics_rejects_bad_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        FontMetrics(tmp_path / "nope.ttf")
    with pytest.raises(ValueError):
        FontMetrics(tmp_path / "x.ttf", size=0)
    bad = tmp_path / "bad.ttf"
    bad.write_bytes(b"not a font")
    with pytest.raises(ValueError):
        FontMetrics(bad)


def test_wrap_with_real_metrics_differs_from_chars():
    metrics = _vazirmatn()
    try:
        text = "مرحبا بالعالم"
        char_lines = wrap_arabic_text(text, 7)
        metric_lines = wrap_arabic_text(text, 60, metrics=metrics)
        assert char_lines == ["مرحبا", "بالعالم"]
        assert all(metrics.width_of(line) <= 60 or " " not in line
                   for line in metric_lines)
        assert "".join(metric_lines).replace(" ", "") == text.replace(" ", "")
    finally:
        metrics.close()
