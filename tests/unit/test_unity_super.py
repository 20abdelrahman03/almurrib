"""Super-refactor batch: strategy engine, fallbacks, diagnostics, UI tags."""

import sys
from pathlib import Path
import types

import pytest

from almurrib.engine_adapters.unity import analysis as A
from almurrib.engine_adapters.unity.analysis import Backend, Capability, Level
from almurrib.engine_adapters.unity.adapter import UnityAdapter
from almurrib.engine_adapters.unity.service import (
    choose_strategy,
    explain_entry,
    suggest_fallbacks,
)
from almurrib.engine_adapters.unity.unityfs import validate_patch
from almurrib.core.errors import ExtractionError
from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
)


def _profile(**over):
    params = dict(game_dir=Path("g"), backend=Backend.MONO)
    params.update(over)
    return A.UnityGameProfile(**params)


def _levels(parse_level):
    return {c: Level.UNSUPPORTED for c in Capability} | {
        Capability.TEXT_ASSET: parse_level}


def test_strategy_il2cpp_is_runtime_with_reasons():
    strategy, reasons = choose_strategy(
        _profile(backend=Backend.IL2CPP), _levels(Level.EXPERIMENTAL))
    assert strategy == "runtime"
    assert any("IL2CPP" in r for r in reasons)


def test_strategy_bundles_force_runtime_overlay():
    strategy, reasons = choose_strategy(
        _profile(bundles=["pack.ab"]), _levels(Level.AUTOMATIC))
    assert strategy == "runtime"
    assert any("runtime overlay selected" in r for r in reasons)


def test_strategy_automatic_clean_mono_is_static():
    strategy, reasons = choose_strategy(
        _profile(), _levels(Level.AUTOMATIC))
    assert strategy == "static"
    assert reasons, "strategy without reasons is silent magic"


def test_strategy_weak_parse_is_runtime():
    strategy, _ = choose_strategy(_profile(), _levels(Level.WITH_WARNING))
    assert strategy == "runtime"


def test_fallbacks_name_real_tools():
    tips = suggest_fallbacks(_profile(backend=Backend.IL2CPP,
                                      bundles=["x.ab"]),
                             _levels(Level.WITH_WARNING), "bundle save failed")
    text = " ".join(tips)
    assert "UABEA" in text and "BepInEx" in text


def test_explain_entry_answers_why_not_arabic():
    ref = SourceRef(file="g/shared.assets", line=7, statement="sheet_entry",
                    extra={"container": "", "class": "TextAsset",
                           "field": "entry[K1]"})
    entry = LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.UNITY, "Hello.", ref),
        engine=EngineType.UNITY, source_text="Hello.",
        translated_text="مرحبا.", status=EntryStatus.TRANSLATED,
        source_refs=[ref], tags=["sheet", "entry"])
    report = explain_entry(entry)
    assert report["source"] == "Hello."
    assert "g/shared.assets:7" in report["location"]
    assert report["translation"] == "SUCCESS"
    assert "sheet_entry" not in report["extraction_method"]  # human words
    assert report["fallback"]


def test_explain_pending_entry():
    ref = SourceRef(file="g/x.assets", line=1, statement="field",
                    extra={"container": "", "class": "MonoBehaviour",
                           "field": "greeting"})
    entry = LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.UNITY, "Hi", ref),
        engine=EngineType.UNITY, source_text="Hi",
        status=EntryStatus.UNTRANSLATED, source_refs=[ref])
    report = explain_entry(entry)
    assert "PENDING" in report["translation"]
    assert report["write_back"]


def test_ui_text_tag_on_ui_shaped_fields():
    found = types.SimpleNamespace(class_name="MonoBehaviour",
                                  object_name="ShopPanel",
                                  field_path="m_text")
    assert "ui_text" in UnityAdapter._tags(found, "m_text")
    found2 = types.SimpleNamespace(class_name="MonoBehaviour",
                                   object_name="AI",
                                   field_path="aggroRange")
    assert "ui_text" not in UnityAdapter._tags(found2, "aggroRange")
    found3 = types.SimpleNamespace(class_name="TextAsset",
                                   object_name="EN_X", field_path="m_Script")
    assert "ui_text" not in UnityAdapter._tags(found3, "m_Script")


def test_apply_handles_dict_shaped_objects(monkeypatch, tmp_path):
    """Real files hand {path_id: reader} dicts, not lists (field find)."""
    from almurrib.engine_adapters.unity import unityfs

    seen = {}

    class FakeUnityPy:
        @staticmethod
        def load(path):
            seen[type(path).__name__] = True
            obj = types.SimpleNamespace(
                type=types.SimpleNamespace(name="TextAsset"), path_id=1)

            class T:
                m_Name = "S"
                m_Script = "plain prose, not a sheet"

                def save(self):
                    pass

            asset = T()
            obj.read = lambda: asset
            fake_file = types.SimpleNamespace(
                objects={1: obj}, container={1: ""}, save=lambda: b"BYTES")
            return types.SimpleNamespace(files={"f": fake_file})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    src = tmp_path / "s.assets"
    src.write_bytes(b"stub")
    dest = tmp_path / "out" / "s.assets"
    out = unityfs.apply_translations(
        src, {("", "m_Script", "plain prose, not a sheet"): "نص"},
        dest_path=dest)
    assert out == dest and dest.read_bytes() == b"BYTES"


def test_validate_loads_bytes_not_path(monkeypatch, tmp_path):
    """Windows locks open files: validation must not hold the staging
    handle (field find: WinError 32 on os.replace)."""
    from almurrib.engine_adapters.unity import unityfs

    seen = {}

    class FakeUnityPy:
        @staticmethod
        def load(path):
            seen[type(path).__name__] = True
            fake_file = types.SimpleNamespace(objects=[], container={})
            return types.SimpleNamespace(files={"f": fake_file})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    target = tmp_path / "x.assets.tmp"
    target.write_bytes(b"stub")
    assert unityfs.validate_patch(target) == 0
    assert seen == {"bytes": True}, seen


def test_visual_arabic_shapes_and_preserves_tags():
    from almurrib.arabic import is_shaped
    from almurrib.engine_adapters.unity.visual import needs_visual, visualize

    assert needs_visual("بدء اللعبة") and not needs_visual("Start Game")
    out = visualize("بدء اللعبة <page> {name} 123")
    assert is_shaped(out)
    assert "<page>" in out and "{name}" in out and "123" in out
    assert visualize("") == ""
    assert visualize("plain") == "plain"


def test_visual_fallback_on_sentinel_collision():
    from almurrib.engine_adapters.unity.visual import visualize

    tricky = "نص \ue000 غريب"
    assert visualize(tricky) == tricky  # logical, never corrupted


def test_write_asset_patch_visual_mode_shapes_blob(monkeypatch, tmp_path):
    from almurrib.arabic import is_shaped
    from almurrib.engine_adapters.unity import unityfs
    from almurrib.engine_adapters.unity.reinject import write_asset_patch
    from almurrib.core.model import EntryStatus

    holder = {}

    class FakeUnityPy:
        @staticmethod
        def load(path):
            if "asset" not in holder:
                from tests.unit.test_unity_phase_b import _Sheet, BLOB

                holder["asset"] = _Sheet(BLOB)
            obj = types.SimpleNamespace(
                type=types.SimpleNamespace(name="TextAsset"), path_id=9)
            obj.read = lambda: holder["asset"]
            fake_file = types.SimpleNamespace(
                objects=[obj], container={9: ""}, save=lambda: b"REBUILT")
            return types.SimpleNamespace(files={"f": fake_file})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    game = tmp_path / "game"
    (game / "D").mkdir(parents=True)
    (game / "D" / "s.assets").write_bytes(b"stub")
    ref = SourceRef(file="D/s.assets", line=1, statement="sheet_entry",
                    extra={"container": "", "field": "entry[K1]"})
    entry = LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.UNITY, "Hello.", ref),
        engine=EngineType.UNITY, source_text="Hello.",
        translated_text="مرحبا بالعالم",
        status=EntryStatus.TRANSLATED, source_refs=[ref])
    out = tmp_path / "patch"
    written = write_asset_patch([entry], game_root=game, output_dir=out,
                                visual_arabic=True)
    assert written
    assert is_shaped(holder["asset"].m_Script)
    assert "مرحبا" not in holder["asset"].m_Script  # logical form replaced
    assert entry.translated_text == "مرحبا بالعالم"  # DB-side stays logical


def test_runtime_bundle_visual_mode(tmp_path):
    from almurrib.arabic import is_shaped
    from almurrib.core.model import EntryStatus
    from almurrib.engine_adapters.unity.runtime import generate_xunity_bundle

    ref = SourceRef(file="g/a.assets", line=1, statement="sheet_entry")
    entry = LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.UNITY, "Hi.", ref),
        engine=EngineType.UNITY, source_text="Hi.",
        translated_text="مرحبا.",
        status=EntryStatus.TRANSLATED, source_refs=[ref])
    bundle = generate_xunity_bundle([entry], tmp_path / "b",
                                    visual_arabic=True)
    assert bundle.pairs == 1
    text = (tmp_path / "b" / "Translation" / "ar" / "Text"
            / "Almurrib_ar.txt").read_text(encoding="utf-8")
    assert is_shaped(text.split("=", 1)[1])


def test_bundle_ships_empty_auto_translations_file(tmp_path):
    """ALT+R reload crashes without the plugin's output file (field find)."""
    from almurrib.core.model import EntryStatus
    from almurrib.engine_adapters.unity.runtime import generate_xunity_bundle

    ref = SourceRef(file="g/a.assets", line=1, statement="sheet_entry")
    entry = LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.UNITY, "Hi.", ref),
        engine=EngineType.UNITY, source_text="Hi.",
        translated_text="مرحبا.",
        status=EntryStatus.TRANSLATED, source_refs=[ref])
    bundle = generate_xunity_bundle([entry], tmp_path / "b")
    auto = (tmp_path / "b" / "Translation" / "ar" / "Text"
            / "_AutoGeneratedTranslations.txt")
    assert auto.is_file() and auto.read_bytes() == b""


def test_validate_patch_refuses_unparseable(monkeypatch, tmp_path):
    from almurrib.engine_adapters.unity import unityfs

    class FakeUnityPy:
        @staticmethod
        def load(path):
            raise RuntimeError("corrupt")

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    bad = tmp_path / "x.assets.tmp"
    bad.write_bytes(b"junk")
    with pytest.raises(ExtractionError, match="does not re-parse"):
        validate_patch(bad)


def test_atomic_write_leaves_no_tmp_on_validation_failure(
        monkeypatch, tmp_path):
    from almurrib.engine_adapters.unity import unityfs

    calls = {"n": 0}

    class FakeUnityPy:
        @staticmethod
        def load(path):
            calls["n"] += 1
            # Validation loads in-memory bytes now: refuse unconditionally.
            raise RuntimeError("reparse says no")
            obj = types.SimpleNamespace(
                type=types.SimpleNamespace(name="TextAsset"), path_id=1)
            holder = {"t": None}

            class T:
                m_Name = "S"
                m_Script = "hi"

                def save(self):
                    pass

            obj.read = lambda: T()
            fake_file = types.SimpleNamespace(
                objects=[obj], container={1: ""}, save=lambda: b"BYTES")
            return types.SimpleNamespace(files={"f": fake_file})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    src = tmp_path / "s.assets"
    src.write_bytes(b"stub")
    dest = tmp_path / "out" / "s.assets"
    with pytest.raises(ExtractionError):
        unityfs.apply_translations(src, {}, dest_path=dest)
    assert not dest.exists() and not dest.with_name("s.assets.tmp").exists()
