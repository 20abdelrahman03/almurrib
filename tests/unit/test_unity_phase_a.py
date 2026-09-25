"""Phase A tests: structured analysis + capability levels + classification."""

from pathlib import Path

import pytest

from almurrib.engine_adapters.unity import analysis as A
from almurrib.engine_adapters.unity import classify as C
from almurrib.engine_adapters.unity.analysis import (
    Backend,
    Capability,
    Level,
)


def _mono_game(root: Path, *, version_marker: bytes = b"UnityFS 2019.4.1f1\x00",
               managed: tuple[str, ...] = ("Assembly-CSharp.dll",
                                           "Unity.TextMeshPro.dll",
                                           "UnityEngine.UI.dll"),
               bundles: bool = False) -> Path:
    game = root / "game"
    data = game / "Game_Data"
    (data / "Managed").mkdir(parents=True)
    (data / "globalgamemanagers").write_bytes(version_marker + b"\x00" * 64)
    for dll in managed:
        (data / "Managed" / dll).write_bytes(b"MZ-stub")
    (data / "sharedassets0.assets").write_bytes(b"UnityFS" + b"\x00" * 64)
    if bundles:
        (data / "StreamingAssets").mkdir(exist_ok=True)
        (data / "StreamingAssets" / "pack.ab").write_bytes(b"UnityFS" + b"\x00")
    return game


def test_analyze_modern_mono(tmp_path):
    profile = A.analyze_game(_mono_game(tmp_path))
    assert profile.backend is Backend.MONO
    assert profile.unity_version == "2019.4.1f1"
    assert profile.textmeshpro and profile.legacy_ui
    assert profile.serialized_assets == 1
    levels = A.capabilities(profile)
    assert levels[Capability.TEXT_ASSET] is Level.AUTOMATIC
    assert levels[Capability.TEXTMESHPRO] is Level.AUTOMATIC
    assert levels[Capability.UNITY_LOCALIZATION] is Level.UNSUPPORTED
    assert levels[Capability.IL2CPP_ANALYSIS] is Level.UNSUPPORTED


def test_analyze_il2cpp(tmp_path):
    game = tmp_path / "g"
    data = game / "G_Data"
    data.mkdir(parents=True)
    (game / "GameAssembly.dll").write_bytes(b"MZ" + b"\x00" * 62)
    (data / "il2cpp_data").mkdir()
    profile = A.analyze_game(game)
    assert profile.backend is Backend.IL2CPP
    assert A.capabilities(profile)[Capability.IL2CPP_ANALYSIS] \
        is Level.EXPERIMENTAL
    assert A.capabilities(profile)[Capability.TEXT_ASSET] \
        is Level.EXPERIMENTAL


def test_analyze_bundles_and_frameworks(tmp_path):
    game = _mono_game(tmp_path, bundles=True)
    (game / "BepInEx").mkdir()
    profile = A.analyze_game(game)
    assert profile.bundles == ["pack.ab"]
    assert profile.bepinex
    assert A.capabilities(profile)[Capability.ASSET_BUNDLE] \
        is Level.WITH_WARNING
    assert A.capabilities(profile)[Capability.RUNTIME_HOOK] \
        is Level.WITH_WARNING


def test_pre5_layout_downgrades_parse(tmp_path):
    game = tmp_path / "g"
    data = game / "G_Data"
    (data / "Managed").mkdir(parents=True)
    (data / "mainData").write_bytes(b"\x00old")
    (data / "Managed" / "Assembly-CSharp.dll").write_bytes(b"MZ")
    profile = A.analyze_game(game)
    assert profile.pre5_era_layout
    assert A.capabilities(profile)[Capability.TEXT_ASSET] \
        is not Level.AUTOMATIC


def test_analyze_not_a_game(tmp_path):
    profile = A.analyze_game(tmp_path / "nope")
    assert profile.backend is Backend.UNKNOWN
    assert all(level is Level.UNSUPPORTED
               for cap, level in A.capabilities(profile).items()
               if cap not in (Capability.TEXT_ASSET, Capability.MONOBEHAVIOUR,
                              Capability.SERIALIZED_ASSET,
                              Capability.RUNTIME_HOOK))


def test_version_label_never_pretends(tmp_path):
    game = _mono_game(tmp_path)
    profile = A.analyze_game(game)
    assert "confidence" in A.version_label(profile)
    unknown = A.analyze_game(tmp_path / "empty")
    assert "unknown" in A.version_label(unknown)


def test_truncated_exe_never_kills_analysis(tmp_path):
    game = _mono_game(tmp_path)
    (game / "Game.exe").write_bytes(b"MZ")  # truncated header
    profile = A.analyze_game(game)  # must not raise
    assert profile.executable == "Game.exe"
    assert profile.arch is None


def test_executable_and_metadata_signals(tmp_path):
    import struct as _struct

    game = _mono_game(tmp_path)
    blob = bytearray(b"MZ" + b"\x00" * 58 + _struct.pack("<I", 0x40))
    blob += b"\x00" * (0x40 - len(blob)) + b"PE\x00\x00" + _struct.pack("<H", 0x8664)
    (game / "Game.exe").write_bytes(bytes(blob))
    meta = game / "Game_Data" / "il2cpp_data" / "Metadata"
    meta.mkdir(parents=True)
    (meta / "global-metadata.dat").write_bytes(b"\x00")
    profile = A.analyze_game(game)
    assert profile.executable == "Game.exe"
    assert profile.metadata_dat


def test_addressable_catalog_parsing(tmp_path):
    import json

    game = _mono_game(tmp_path)
    streaming = game / "Game_Data" / "StreamingAssets"
    streaming.mkdir(exist_ok=True)
    (streaming / "catalog_1.json").write_text(json.dumps(
        {"m_InternalIds": ["aa/bundle_a.bundle", "bundle_b.bundle"]}))
    (streaming / "catalog_bad.json").write_text("{not json")
    profile = A.analyze_game(game)
    assert profile.addressables
    assert sorted(profile.addressable_bundles) == [
        "bundle_a.bundle", "bundle_b.bundle"]
    assert any("unreadable catalog" in e for e in profile.evidence)


def test_pe_arch_detection(tmp_path):
    import struct

    game = tmp_path / "g"
    game.mkdir()
    # Minimal MZ + PE header with x64 machine id.
    blob = bytearray(b"MZ" + b"\x00" * 58 + struct.pack("<I", 0x40))
    blob += b"\x00" * (0x40 - len(blob)) + b"PE\x00\x00" + struct.pack("<H", 0x8664)
    (game / "Game.exe").write_bytes(bytes(blob))
    assert A.analyze_game(game).arch == "x64"


@pytest.mark.parametrize("text,verdict,reason", [
    ("550e8400-e29b-41d4-a716-446655440000", C.Verdict.TECHNICAL, "GUID"),
    ("https://example.com/x", C.Verdict.TECHNICAL, "URL"),
    ("Assets/Prefabs/Hero.prefab", C.Verdict.TECHNICAL, "file path"),
    ("Assembly-CSharp.dll", C.Verdict.TECHNICAL, "assembly"),
    ("Standard.shader", C.Verdict.TECHNICAL, "shader"),
    ("12345", C.Verdict.TECHNICAL, "numeric ID"),
    ("QUEST_042", C.Verdict.TECHNICAL, "internal ID"),
    ("__debug_draw", C.Verdict.TECHNICAL, "debug"),
    ("UnityEngine.UI.Text", C.Verdict.TECHNICAL, "dotted"),
    ("fire_sword", C.Verdict.POSSIBLY, "identifier"),
    ("OK", C.Verdict.POSSIBLY, "tiny"),
    ("My dapper gadfly, care for charms?", C.Verdict.LIKELY, "prose"),
    ("مرحبا بالعالم", C.Verdict.LIKELY, "prose"),
])
def test_classify(text, verdict, reason):
    result = C.classify_candidate(text)
    assert result.verdict is verdict
    assert reason in result.reason
