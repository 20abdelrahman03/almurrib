"""Core domain model tests."""

from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
    content_hash,
)


def _sample_entry() -> LocalizationEntry:
    ref = SourceRef(file="game/script.rpy", line=9, statement="say")
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, "Hello!", ref),
        engine=EngineType.RENPY,
        source_text="Hello!",
        speaker="Eileen",
        context="speaker:Eileen; file:game/script.rpy",
        source_refs=[ref],
        tags=["dialogue"],
    )


def test_content_hash_is_deterministic_and_separator_safe():
    a = content_hash("ab", "c")
    b = content_hash("a", "bc")
    assert a != b  # unit separator prevents ambiguity
    assert content_hash("x", None, "y") == content_hash("x", None, "y")


def test_make_id_is_stable_for_same_location_and_text():
    ref = SourceRef(file="game/script.rpy", line=9)
    id1 = LocalizationEntry.make_id(EngineType.RENPY, "Hello!", ref)
    id2 = LocalizationEntry.make_id(EngineType.RENPY, "Hello!", ref)
    assert id1 == id2
    other_ref = SourceRef(file="game/script.rpy", line=10)
    assert LocalizationEntry.make_id(EngineType.RENPY, "Hello!", other_ref) != id1


def test_fingerprint_ignores_location():
    entry = _sample_entry()
    moved = LocalizationEntry.from_dict({
        **entry.to_dict(),
        "source_refs": [{"file": "game/other.rpy", "line": 1, "statement": "say", "extra": {}}],
    })
    assert moved.fingerprint == entry.fingerprint


def test_entry_round_trip_serialization():
    entry = _sample_entry()
    restored = LocalizationEntry.from_dict(entry.to_dict())
    assert restored.to_dict() == entry.to_dict()
    assert restored.status == EntryStatus.UNTRANSLATED
    assert restored.engine is EngineType.RENPY
    assert restored.source_refs[0].line == 9
