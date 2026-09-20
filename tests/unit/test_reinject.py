"""Ren'Py reinjection tests (string-translation form)."""

import pytest

from almurrib.core.errors import ExportError
from almurrib.core.model import EngineType, EntryStatus, LocalizationEntry, SourceRef
from almurrib.engine_adapters.renpy.reinject import (
    generate_translation_files,
    write_translation_patch,
)


def _say(text: str, translation: str | None, line: int, speaker: str | None = None):
    ref = SourceRef(file="game/script.rpy", line=line, statement="say")
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY,
        source_text=text,
        translated_text=translation,
        speaker=speaker,
        source_refs=[ref],
        status=EntryStatus.TRANSLATED if translation else EntryStatus.UNTRANSLATED,
    )


def _menu(text: str, translation: str, line: int):
    ref = SourceRef(file="game/script.rpy", line=line, statement="menu")
    return LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RENPY, text, ref),
        engine=EngineType.RENPY,
        source_text=text,
        translated_text=translation,
        source_refs=[ref],
        status=EntryStatus.TRANSLATED,
    )


def test_translated_entries_generate_string_pairs():
    entries = [
        _say("Hello!", "مرحبًا!", 9, speaker="Eileen"),
        _menu("Yes", "نعم", 16),
    ]
    files = generate_translation_files(entries, target_lang="arabic")

    assert "game/tl/arabic/strings.rpy" in files
    content = files["game/tl/arabic/strings.rpy"]
    assert "translate arabic strings:" in content
    assert 'old "Hello!"' in content
    assert 'new "مرحبًا!"' in content
    assert 'old "Yes"' in content
    assert 'new "نعم"' in content
    # provenance comments help human review
    assert "# game/script.rpy:9 [Eileen]" in content


def test_untranslated_entries_are_skipped():
    files = generate_translation_files(
        [_say("Untranslated", None, 1)], target_lang="arabic"
    )
    assert files == {}


def test_flagged_entries_keep_qa_comment():
    entry = _say("Hi {name}!", "مرحبًا!", 3)
    entry.qa_flags.append("placeholder_missing:{name}")
    files = generate_translation_files([entry], target_lang="arabic")
    content = files["game/tl/arabic/strings.rpy"]
    assert "# QA: placeholder_missing:{name}" in content


def test_quoting_escapes_special_chars():
    entry = _say('He said "hi"', 'قال "مرحبا"', 5)
    files = generate_translation_files([entry], target_lang="arabic")
    content = files["game/tl/arabic/strings.rpy"]
    assert 'old "He said \\"hi\\""' in content


def test_write_patch_never_touches_original(tmp_path):
    game_dir = tmp_path / "game_root"
    original = game_dir / "game" / "script.rpy"
    original.parent.mkdir(parents=True)
    original.write_text('e "Hello!"', encoding="utf-8")

    out_dir = tmp_path / "patch"
    written = write_translation_patch(
        [_say("Hello!", "مرحبًا!", 1, speaker="Eileen")],
        target_lang="arabic",
        output_dir=out_dir,
    )

    assert written and all(p.exists() for p in written)
    assert original.read_text(encoding="utf-8") == 'e "Hello!"'
    assert (out_dir / "game" / "tl" / "arabic" / "strings.rpy").exists()


def test_write_patch_requires_translations(tmp_path):
    with pytest.raises(ExportError):
        write_translation_patch(
            [_say("No translation", None, 1)],
            target_lang="arabic",
            output_dir=tmp_path / "patch",
        )
