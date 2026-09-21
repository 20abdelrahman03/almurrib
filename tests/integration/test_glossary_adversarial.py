"""Adversarial tests for glossary, context, metrics, wrap, RTL resources."""

import pytest

from almurrib.arabic.fonts import FontMetrics
from almurrib.arabic.wrap import wrap_arabic_text
from almurrib.core.glossary import (
    Glossary,
    GlossaryEntry,
    build_translation_context,
    export_csv,
    export_json,
    glossary_qa_check,
    import_csv,
    import_entries,
    import_json,
    merge_glossaries,
)
from almurrib.core.model import EngineType, LocalizationEntry, SourceRef


def _entry(text: str, speaker: str | None = None) -> LocalizationEntry:
    ref = SourceRef(file="g/s.rpy", line=1)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY, source_text=text, speaker=speaker,
        context="file:g/s.rpy", source_refs=[ref])


# -- glossary hostility ---------------------------------------------------------------

def test_overlapping_terms_longest_wins():
    glossary = Glossary([
        GlossaryEntry(source_term="novel", target_term="رواية"),
        GlossaryEntry(source_term="visual novel", target_term="رواية مرئية"),
        GlossaryEntry(source_term="visual", target_term="مرئي"),
    ])
    matches = glossary.lookup("a visual novel")
    assert [m.entry.source_term for m in matches] == ["visual novel"]


def test_case_variants_and_whitespace_aliases():
    glossary = Glossary([GlossaryEntry(
        source_term="Sylvie", target_term="سيلفي", aliases=("  sylvie! ",))])
    assert glossary.lookup("SYLVIE!") != []
    # alias with punctuation still boundary-safe
    assert glossary.lookup("xSYLVIEx") == []


def test_disabled_and_empty_aliases_ignored():
    glossary = Glossary([
        GlossaryEntry(source_term="Off", target_term="x", enabled=False),
        GlossaryEntry(source_term="On", target_term="نعم", aliases=("", "  ")),
    ])
    assert glossary.lookup("off and on") != []
    assert all(m.entry.source_term == "On" for m in glossary.lookup("off and on"))


def test_malformed_import_rows_skipped_with_reasons():
    raw = [
        {"source_term": "A", "target_term": "1"},
        {"source_term": "A", "target_term": "2"},
        {"source_term": "B"},  # missing target
        "not-a-dict",
        {"source_term": "C", "target_term": "3", "type": "bogus"},
        {"source_term": "D", "target_term": "4", "gender": "bogus"},
    ]
    glossary, skipped = import_entries(raw)
    assert len(glossary.entries) == 1
    assert len(skipped) == 5
    assert all({"index", "term", "reason"} <= set(s) for s in skipped)


def test_csv_malformed_and_empty_rows():
    glossary, skipped = import_csv("source_term,target_term\nA,1\n,2\nB,")
    assert [e.source_term for e in glossary.entries] == ["A"]
    with pytest.raises(ValueError):
        import_json("not json{")


def test_json_csv_round_trip_stable():
    glossary = Glossary([
        GlossaryEntry(source_term="A\nB", target_term="1", notes='q"q',
                      aliases=("x|y",)),
    ])
    again, skipped = import_json(export_json(glossary))
    assert skipped == []
    assert again.entries[0].aliases == ("x|y",)
    assert again.entries[0].source_term == "A\nB"
    again_csv, skipped_csv = import_csv(export_csv(glossary))
    assert skipped_csv == []


def test_merge_deterministic_regardless_of_order():
    first = Glossary([GlossaryEntry(source_term="b", target_term="2"),
                      GlossaryEntry(source_term="a", target_term="1")])
    merged = merge_glossaries(first, Glossary())
    assert [e.source_term for e in merged.enabled()] == ["b", "a"]
    assert merged.revision() == Glossary(list(reversed(first.entries))).revision()


def test_qa_never_crashes_on_hostile_matches():
    matches = Glossary([GlossaryEntry(source_term="x" * 500, target_term="y")]
                       ).lookup("x" * 500)
    flags = glossary_qa_check("x" * 500, "", matches)
    assert isinstance(flags, list)


# -- context hostility ---------------------------------------------------------------------

def test_context_unknown_speaker_and_empty_glossary():
    context = build_translation_context(_entry("Hi", speaker="???"), Glossary())
    assert context.speaker_gender is None
    assert context.glossary_terms == ()
    context2 = build_translation_context(_entry("Hi"), None)
    assert context2.speaker is None


# -- metrics hostility --------------------------------------------------------------------------

def _vazirmatn():
    from pathlib import Path

    font = Path(__file__).resolve().parents[2] / "fixtures" / "fonts" / \
        "Vazirmatn-Variable.ttf"
    if not font.exists():
        pytest.skip("bundled Vazirmatn fixture not present")
    return FontMetrics(font, size=16)


def test_metrics_missing_glyph_fallback_and_urls():
    metrics = _vazirmatn()
    try:
        assert metrics.glyph_width("😀") == metrics.glyph_width("😀")  # stable
        url = "https://example.com/very/long/path?x=1"
        lines = wrap_arabic_text(f"زر {url} هنا", 40, metrics=metrics)
        assert "".join(lines).replace(" ", "") == f"زر{url}هنا".replace(" ", "")
        assert metrics.width_of("") == 0
    finally:
        metrics.close()


def test_metrics_huge_and_zero_widths():
    metrics = _vazirmatn()
    try:
        assert wrap_arabic_text("مرحبا بالعالم", 10**6, metrics=metrics) == \
            ["مرحبا بالعالم"]
        with pytest.raises(ValueError):
            wrap_arabic_text("x", 0, metrics=metrics)
        assert metrics.line_height() > 0
    finally:
        metrics.close()
