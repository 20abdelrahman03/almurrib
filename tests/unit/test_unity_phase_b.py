"""Phase B tests: sheet element write-back, staleness refusal, inspection."""

import sys
import types
from pathlib import Path

import pytest

from almurrib.core.errors import ExtractionError
from almurrib.engine_adapters.unity import unityfs
from almurrib.engine_adapters.unity.unityfs import (
    _apply_text_asset,
    inspect_asset,
    replace_sheet_elements,
)

BLOB = ('<entries><entry name="K1">Hello.</entry>'
        '<entry name="K2">A &lt;page&gt; break.</entry></entries>')


def test_replace_basic_and_count():
    new_blob, count = replace_sheet_elements(BLOB, {"K1": "مرحبا."})
    assert count == 1
    assert '<entry name="K1">مرحبا.</entry>' in new_blob
    assert '<entry name="K2">A &lt;page&gt; break.</entry>' in new_blob


def test_replace_escapes_translation_markup():
    # Translated markup round-trips as entities (mirrors extraction).
    new_blob, _ = replace_sheet_elements(BLOB, {"K1": "أهلا <page> يا"})
    assert "<entry name=\"K1\">أهلا &lt;page&gt; يا</entry>" in new_blob
    assert "<entry name=\"K1\">أهلا <page> يا</entry>" not in new_blob


def test_replace_unknown_key_untouched():
    new_blob, count = replace_sheet_elements(BLOB, {"NOPE": "x"})
    assert (new_blob, count) == (BLOB, 0)


class _Sheet:
    def __init__(self, script):
        self.m_Script = script
        self.saved = False

    def save(self):
        self.saved = True


def test_apply_element_end_to_end():
    asset = _Sheet(BLOB)
    problems = _apply_text_asset(
        asset, "", {("", "entry[K1]", "Hello."): "مرحبا."})
    assert problems == []
    assert asset.saved
    assert "مرحبا." in asset.m_Script
    assert "A &lt;page&gt; break." in asset.m_Script  # neighbor preserved


def test_apply_skips_foreign_keys_silently_per_object():
    # Per-object matching stages only what THIS blob holds; staleness is
    # judged file-wide (unapplied_element_keys), so sibling-language
    # sheets never poison each other.
    asset = _Sheet(BLOB)
    problems = _apply_text_asset(
        asset, "", {("", "entry[GHOST]", "Hi"): "مرحبا"})
    assert problems == [] and not asset.saved
    assert asset.m_Script == BLOB


def test_apply_changed_source_skipped_per_object():
    asset = _Sheet(BLOB)
    problems = _apply_text_asset(
        asset, "", {("", "entry[K1]", "WRONG OLD"): "مرحبا"})
    assert problems == [] and not asset.saved


def test_unapplied_keys_reported_file_wide():
    from almurrib.engine_adapters.unity.unityfs import unapplied_element_keys

    assert unapplied_element_keys(
        [("", BLOB)], {("", "entry[GHOST]", "Hi"): "x"}) != []
    assert unapplied_element_keys(
        [("", BLOB)], {("", "entry[K1]", "Hello."): "x"}) == []


def test_sibling_sheets_route_to_matching_blob():
    """EN + FR sheets share keys: EN translations land in the EN blob."""
    from almurrib.engine_adapters.unity.unityfs import unapplied_element_keys

    fr = BLOB.replace("Hello.", "Bonjour.").replace(
        "A &lt;page&gt; break.", "Une pause.")
    # What apply_translations checks file-wide after per-object staging:
    blobs = [("", BLOB), ("", fr)]
    reps = {("", "entry[K1]", "Hello."): "مرحبا."}
    assert unapplied_element_keys(blobs, reps) == []
    # ...but the FR blob alone cannot satisfy it:
    assert unapplied_element_keys([("", fr)], reps) != []


def test_apply_mixed_whole_and_element_prefers_elements_loudly():
    asset = _Sheet(BLOB)
    problems = _apply_text_asset(asset, "", {
        ("", "entry[K1]", "Hello."): "مرحبا.",
        ("", "m_Script", BLOB): "whole?",
    })
    assert any("mixed" in p for p in problems)
    assert asset.saved and "مرحبا." in asset.m_Script


def test_apply_ignores_other_containers():
    asset = _Sheet(BLOB)
    problems = _apply_text_asset(
        asset, "Res", {("Other", "entry[K1]", "Hello."): "مرحبا."})
    assert problems == [] and not asset.saved


def _env_with_sheet(blob):
    holder = {}

    class FakeUnityPy:
        @staticmethod
        def load(path):
            if path == "BOOM":
                raise RuntimeError("cannot parse")
            obj = types.SimpleNamespace(type=types.SimpleNamespace(name="TextAsset"),
                                        path_id=1)
            # Stable file: repeated loads see the same asset object.
            if "asset" not in holder:
                holder["asset"] = _Sheet(blob)
            obj.read = lambda: holder["asset"]
            fake_file = types.SimpleNamespace(
                objects=[obj], container={1: ""},
                save=lambda: b"REBUILT")
            return types.SimpleNamespace(files={"f": fake_file})

    mod = types.ModuleType("UnityPy")
    mod.load = FakeUnityPy.load
    return mod, holder


def test_sheet_round_trip_through_apply_translations(monkeypatch, tmp_path):
    mod, holder = _env_with_sheet(BLOB)
    monkeypatch.setitem(sys.modules, "UnityPy", mod)
    src = tmp_path / "s.assets"
    src.write_bytes(b"stub")
    dest = tmp_path / "out" / "s.assets"
    unityfs.apply_translations(
        src, {("", "entry[K2]", "A <page> break."): "أ <page> ب"},
        dest_path=dest)
    assert holder["asset"].saved
    assert dest.read_bytes() == b"REBUILT"
    # Reparse the written blob: neighbor intact, target replaced+escaped.
    assert "أ &lt;page&gt; ب" in holder["asset"].m_Script
    assert 'name="K1">Hello.' in holder["asset"].m_Script


def test_stale_sheet_refuses_whole_file(monkeypatch, tmp_path):
    mod, _ = _env_with_sheet(BLOB)
    monkeypatch.setitem(sys.modules, "UnityPy", mod)
    src = tmp_path / "s.assets"
    src.write_bytes(b"stub")
    with pytest.raises(ExtractionError, match="write-back refused"):
        unityfs.apply_translations(
            src, {("", "entry[K1]", "STALE"): "مرحبا"},
            dest_path=tmp_path / "o.assets")


def test_inspect_unreadable_is_shape_not_crash(monkeypatch):
    mod, _ = _env_with_sheet(BLOB)
    monkeypatch.setitem(sys.modules, "UnityPy", mod)
    ok_report = inspect_asset(Path("s.assets"))
    assert ok_report.loadable and ok_report.object_count == 1
    assert ok_report.classes == {"TextAsset": 1}
    bad_report = inspect_asset(Path("BOOM"))
    assert not bad_report.loadable and bad_report.error
