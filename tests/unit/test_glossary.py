"""Glossary unit tests: model, lookup, context, merge, import/export, QA."""

import pytest

from almurrib.core.glossary import (
    GLOBAL_PROJECT_ID,
    Glossary,
    GlossaryEntry,
    TranslationContext,
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
    ref = SourceRef(file="game/s.rpy", line=1)
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY, source_text=text, speaker=speaker,
        context="file:game/s.rpy", source_refs=[ref])


def _glossary() -> Glossary:
    return Glossary([
        GlossaryEntry(source_term="Sylvie", target_term="سيلفي",
                      type="character", gender="female", style="colloquial"),
        GlossaryEntry(source_term="visual novel", target_term="رواية مرئية"),
        GlossaryEntry(source_term="Me", target_term="أنا", type="character",
                      gender="male", aliases=("myself",)),
    ])


# -- model validation ---------------------------------------------------------------

def test_entry_validation():
    with pytest.raises(ValueError):
        GlossaryEntry(source_term="", target_term="x")
    with pytest.raises(ValueError):
        GlossaryEntry(source_term="x", target_term="  ")
    with pytest.raises(ValueError):
        GlossaryEntry(source_term="x", target_term="y", type="nope")
    with pytest.raises(ValueError):
        GlossaryEntry(source_term="x", target_term="y", gender="nope")
    with pytest.raises(ValueError):
        GlossaryEntry(source_term="x", target_term="y", style="nope")


def test_glossary_round_trip_serialization():
    entry = _glossary().entries[0]
    assert GlossaryEntry.from_dict(entry.to_dict()).to_dict() == entry.to_dict()


# -- lookup -----------------------------------------------------------------------------------

def test_lookup_longest_match_and_boundaries():
    glossary = Glossary([
        GlossaryEntry(source_term="novel", target_term="رواية"),
        GlossaryEntry(source_term="visual novel", target_term="رواية مرئية"),
    ])
    matches = glossary.lookup("a visual novel, novelty aside")
    assert [(m.entry.source_term, m.matched_text) for m in matches] == [
        ("visual novel", "visual novel")]
    # "Me" must not match inside "memory".
    me = Glossary([GlossaryEntry(source_term="Me", target_term="أنا")])
    assert [m.matched_text for m in me.lookup("bring me memory")] == ["me"]
    assert me.lookup("memory") == []


def test_lookup_case_insensitive_aliases_and_disabled():
    glossary = _glossary()
    assert glossary.lookup("SYLVIE")[0].entry.target_term == "سيلفي"
    assert glossary.lookup("talked about myself")[0].matched_text == "myself"
    off = Glossary([GlossaryEntry(source_term="x", target_term="y", enabled=False)])
    assert off.lookup("x marks") == []


def test_character_for_matches_aliases():
    glossary = _glossary()
    assert glossary.character_for("Sylvie").gender == "female"  # type: ignore[union-attr]
    assert glossary.character_for("myself").source_term == "Me"  # type: ignore[union-attr]
    assert glossary.character_for(None) is None
    assert glossary.character_for("Nobody") is None


def test_revision_stable_and_sensitive():
    first, second = _glossary(), _glossary()
    assert first.revision() == second.revision()
    changed = Glossary(first.entries[1:])
    assert changed.revision() != first.revision()


# -- context ---------------------------------------------------------------------------------------

def test_build_translation_context():
    context = build_translation_context(
        _entry("Hi Sylvie, read this visual novel", speaker="Me"), _glossary())
    assert isinstance(context, TranslationContext)
    assert context.speaker_gender == "male"
    assert context.speaker_style is None
    assert context.glossary_terms == (
        ("Sylvie", "سيلفي"), ("visual novel", "رواية مرئية"))
    assert context.nearby_context == "file:game/s.rpy"


def test_context_without_glossary():
    context = build_translation_context(_entry("Hi", speaker="Me"), None)
    assert context.speaker == "Me"
    assert context.glossary_terms == ()


def test_merge_project_wins():
    project = Glossary([GlossaryEntry(source_term="Sylvie", target_term="سيلفي-مشروع",
                                      project_id=7)])
    shared = Glossary([GlossaryEntry(source_term="Sylvie", target_term="سيلفي"),
                       GlossaryEntry(source_term="Me", target_term="أنا")])
    merged = merge_glossaries(project, shared)
    by_term = {e.source_term: e.target_term for e in merged.enabled()}
    assert by_term == {"Sylvie": "سيلفي-مشروع", "Me": "أنا"}


def test_project_disable_suppresses_global():
    project = Glossary([GlossaryEntry(source_term="Sylvie", target_term="x",
                                      enabled=False, project_id=7)])
    shared = Glossary([GlossaryEntry(source_term="Sylvie", target_term="سيلفي")])
    merged = merge_glossaries(project, shared)
    assert merged.lookup("hi Sylvie") == []


# -- import / export -------------------------------------------------------------------------------------

def test_json_round_trip_with_conflict_and_malformed():
    glossary, skipped = import_json(export_json(_glossary()))
    assert skipped == []
    assert len(glossary.entries) == 3
    dup = {
        "format": "almurrib-glossary", "format_version": 1,
        "entries": [
            {"source_term": "A", "target_term": "1"},
            {"source_term": "a", "target_term": "2"},  # conflict
            {"source_term": "", "target_term": "x"},  # malformed
        ],
    }
    import json

    glossary2, skipped2 = import_json(json.dumps(dup))
    assert len(glossary2.entries) == 1
    assert len(skipped2) == 2
    assert any("conflict" in s["reason"] for s in skipped2)


def test_json_rejects_wrong_format_and_garbage():
    with pytest.raises(ValueError):
        import_json('{"format": "nope", "entries": []}')
    with pytest.raises(ValueError):
        import_json("{broken")


def test_csv_round_trip():
    glossary, skipped = import_csv(export_csv(_glossary()))
    assert skipped == []
    by_term = {e.source_term: e for e in glossary.entries}
    assert by_term["Sylvie"].gender == "female"
    assert by_term["Me"].aliases == ("myself",)
    assert glossary.entries[0].enabled is True


# -- glossary QA -----------------------------------------------------------------------------------------------

def test_name_mismatch_is_error_term_is_warning():
    matches = _glossary().lookup("Sylvie reads a visual novel")
    flags = glossary_qa_check("Sylvie reads a visual novel",
                              "سيلفي تقرأ رواية", matches)
    mismatches = [f for f in flags if f.rule_id == "glossary.mismatch"]
    assert mismatches  # visual novel term missing
    assert all(f.severity == "warning" for f in mismatches)

    silent = glossary_qa_check("Me", "أنا", _glossary().lookup("Me"))
    assert silent == []
    broken = glossary_qa_check("Hi Sylvie", "أهلا نادية",
                               _glossary().lookup("Hi Sylvie"))
    kinds = {f.rule_id: f.severity for f in broken}
    assert kinds.get("glossary.mismatch") == "error"  # character: error


def test_name_present_passes_despite_inflection():
    matches = _glossary().lookup("Hi Sylvie")
    assert glossary_qa_check("Hi Sylvie", "أهلا سيلفى", matches) == []


def test_forbidden_variant_is_error():
    glossary = Glossary([GlossaryEntry(
        source_term="Sylvie", target_term="سيلفي", type="character",
        forbidden=("سيلفيا",))])
    matches = glossary.lookup("Hi Sylvie")
    flags = glossary_qa_check("Hi Sylvie", "أهلا سيلفيا", matches)
    assert any(f.rule_id == "glossary.forbidden" and f.severity == "error"
               for f in flags)


def test_no_matches_no_flags():
    assert glossary_qa_check("plain text", "نص عادي", []) == []
