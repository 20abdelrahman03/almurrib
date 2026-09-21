"""Structured Unity game analysis (stdlib only, no UnityPy needed).

``analyze_game`` turns a game folder into a :class:`UnityGameProfile`:
version, scripting backend (Mono/IL2CPP), architecture, managed
assemblies (which reveal TMP/UI/Localization/Addressables packages),
content layout (StreamingAssets/Resources/bundles), and resident
mod frameworks (BepInEx/MelonLoader/…). :func:`capabilities` maps the
profile onto the 12-capability support model with honest levels —
never "supported" just because Unity was detected.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from almurrib.engine_adapters.unity.unityfs import sniff_version


class Backend(str, Enum):
    MONO = "mono"
    IL2CPP = "il2cpp"
    UNKNOWN = "unknown"


class Capability(str, Enum):
    TEXT_ASSET = "text_asset"
    MONOBEHAVIOUR = "monobehaviour"
    UNITY_UI_TEXT = "unity_ui_text"
    TEXTMESHPRO = "textmeshpro"
    UNITY_LOCALIZATION = "unity_localization"
    ADDRESSABLES = "addressables"
    ASSET_BUNDLE = "asset_bundle"
    SERIALIZED_ASSET = "serialized_asset"
    MONO_ASSEMBLY_STRINGS = "mono_assembly_strings"
    IL2CPP_ANALYSIS = "il2cpp_analysis"
    RUNTIME_HOOK = "runtime_hook"
    FONT_OVERRIDE = "font_override"


class Level(str, Enum):
    AUTOMATIC = "automatic"
    WITH_WARNING = "supported_with_warning"
    EXPERIMENTAL = "experimental"
    UNSUPPORTED = "unsupported"


@dataclass
class UnityGameProfile:
    """Everything we can say about a Unity game without parsing assets."""

    game_dir: Path
    data_dirs: list[str] = field(default_factory=list)
    unity_version: str | None = None
    backend: Backend = Backend.UNKNOWN
    arch: str | None = None
    managed_assemblies: list[str] = field(default_factory=list)
    streaming_assets: bool = False
    resources_dirs: int = 0
    # Unity <= 4.x ships `mainData`; Unity >= 5 ships `globalgamemanagers`.
    # mainData-without-globalgamemanagers is a static pre-5.x era signal
    # (those builds lack embedded typetrees — verified on Slender 2012).
    pre5_era_layout: bool = False
    bundles: list[str] = field(default_factory=list)
    serialized_assets: int = 0
    addressables: bool = False
    localization_package: bool = False
    textmeshpro: bool = False
    legacy_ui: bool = False
    bepinex: bool = False
    melonloader: bool = False
    other_frameworks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


# Managed assembly names that reveal optional Unity packages/features.
_ASSEMBLY_SIGNALS = {
    "Unity.TextMeshPro.dll": ("textmeshpro", "TextMeshPro assemblies"),
    "Unity.Localization.dll": ("localization_package", "Unity Localization package"),
    "Unity.Addressables.dll": ("addressables", "Addressables assemblies"),
    "UnityEngine.UI.dll": ("legacy_ui", "legacy Unity UI assemblies"),
    "Unity.ResourceManager.dll": ("addressables", "Addressables resource manager"),
}


def analyze_game(game_dir: Path) -> UnityGameProfile:
    """Build a structured profile of a Unity game folder (never raises)."""
    game_dir = Path(game_dir)
    profile = UnityGameProfile(game_dir=game_dir)
    if not game_dir.is_dir():
        profile.evidence.append("not a directory")
        return profile

    data_dirs = sorted(p for p in game_dir.glob("*_Data") if p.is_dir())
    profile.data_dirs = [p.name for p in data_dirs]
    if data_dirs:
        profile.evidence.append(f"Unity data dir ({data_dirs[0].name}/)")
    managers = {p.name for d in data_dirs for p in d.iterdir()
                if p.is_file()}
    if "mainData" in managers and "globalgamemanagers" not in managers:
        profile.pre5_era_layout = True
        profile.evidence.append("pre-5.x layout (mainData, no globalgamemanagers)")

    profile.unity_version = _detect_version(data_dirs)
    _detect_backend(game_dir, data_dirs, profile)
    profile.arch = _detect_arch(game_dir, profile)
    _scan_managed(data_dirs, profile)
    _scan_content(game_dir, data_dirs, profile)
    _scan_frameworks(game_dir, profile)
    return profile


def _detect_version(data_dirs: list[Path]) -> str | None:
    for data_dir in data_dirs:
        for name in ("globalgamemanagers", "mainData", "data.unity3d"):
            candidate = data_dir / name
            if candidate.is_file():
                version = sniff_version(candidate)
                if version and version != "unknown":
                    return version
    return None


def _detect_backend(game_dir: Path, data_dirs: list[Path],
                    profile: UnityGameProfile) -> None:
    for data_dir in data_dirs:
        managed = data_dir / "Managed"
        if managed.is_dir() and any(managed.glob("*.dll")):
            profile.backend = Backend.MONO
            profile.evidence.append("Mono backend (Managed/*.dll present)")
            return
    if list(game_dir.glob("GameAssembly.dll")) or any(
            (d / "il2cpp_data").is_dir() for d in data_dirs):
        profile.backend = Backend.IL2CPP
        profile.evidence.append("IL2CPP backend (GameAssembly/il2cpp_data)")
        return
    profile.evidence.append("scripting backend unknown")


_PE_MACHINES = {0x014C: "x86", 0x8664: "x64", 0xAA64: "arm64"}


def _detect_arch(game_dir: Path, profile: UnityGameProfile) -> str | None:
    """Read the PE machine field of the game exe or GameAssembly (stdlib)."""
    candidates = sorted(game_dir.glob("*.exe"))
    candidates += sorted(game_dir.glob("GameAssembly.dll"))
    for exe in candidates:
        try:
            with open(exe, "rb") as handle:
                if handle.read(2) != b"MZ":
                    continue
                handle.seek(0x3C)
                (pe_offset,) = struct.unpack("<I", handle.read(4))
                handle.seek(pe_offset + 4)
                (machine,) = struct.unpack("<H", handle.read(2))
        except OSError:
            continue
        arch = _PE_MACHINES.get(machine)
        if arch:
            profile.evidence.append(f"architecture {arch} ({exe.name})")
            return arch
    return None


def _scan_managed(data_dirs: list[Path], profile: UnityGameProfile) -> None:
    for data_dir in data_dirs:
        managed = data_dir / "Managed"
        if not managed.is_dir():
            continue
        for dll in sorted(managed.glob("*.dll")):
            profile.managed_assemblies.append(dll.name)
    seen = set(profile.managed_assemblies)
    for dll_name, (flag, label) in _ASSEMBLY_SIGNALS.items():
        if dll_name in seen:
            setattr(profile, flag, True)
            profile.evidence.append(label)


def _scan_content(game_dir: Path, data_dirs: list[Path],
                  profile: UnityGameProfile) -> None:
    for data_dir in data_dirs:
        if (data_dir / "StreamingAssets").is_dir():
            profile.streaming_assets = True
            streaming = data_dir / "StreamingAssets"
            if (streaming / "aa").is_dir() or list(streaming.glob("catalog_*.json")):
                profile.addressables = True
                profile.evidence.append("Addressables catalogs in StreamingAssets")
        profile.resources_dirs += sum(
            1 for _ in data_dir.rglob("Resources") if _.is_dir())
        profile.serialized_assets += len(list(data_dir.glob("*.assets")))
        profile.serialized_assets += len(
            [p for p in data_dir.glob("level*")
             if p.is_file() and not p.suffix])
        profile.bundles += sorted(
            p.name for p in data_dir.rglob("*.ab") if p.is_file())
        profile.bundles += sorted(
            p.name for p in data_dir.rglob("*.unity3d") if p.is_file())
    if profile.streaming_assets:
        profile.evidence.append("StreamingAssets present")
    if profile.bundles:
        profile.evidence.append(f"{len(profile.bundles)} asset bundle(s)")


def _scan_frameworks(game_dir: Path, profile: UnityGameProfile) -> None:
    if (game_dir / "BepInEx").is_dir() or \
            list(game_dir.glob("doorstop_config.ini")):
        profile.bepinex = True
        profile.evidence.append("BepInEx already installed")
    if (game_dir / "MelonLoader").is_dir() or (game_dir / "Mods").is_dir():
        profile.melonloader = True
        profile.evidence.append("MelonLoader/Mods present")
    for marker in ("ReiPatcher", "IPA", "Plugins", "AutoTranslator",
                   "BepInEx-IL2CPP"):
        if (game_dir / marker).is_dir():
            profile.other_frameworks.append(marker)
    if profile.other_frameworks:
        profile.evidence.append(
            "other frameworks: " + ", ".join(profile.other_frameworks))


def _version_tuple(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    nums = re.findall(r"\d+", version)
    return tuple(int(n) for n in nums[:3])


def capabilities(profile: UnityGameProfile) -> dict[Capability, Level]:
    """Map a profile onto honest per-capability support levels."""
    known_old = (bool(profile.unity_version) and
                   _version_tuple(profile.unity_version) < (5, 0, 0)) \
        or profile.pre5_era_layout
    mono = profile.backend is Backend.MONO
    il2cpp = profile.backend is Backend.IL2CPP
    levels: dict[Capability, Level] = {}

    # Unknown version is NOT old: extraction itself is the probe (it
    # either yields entries or fails loudly with a clear diagnostic).
    # Only a known pre-5.x version downgrades parse capabilities.
    parse_ok = mono and not known_old
    levels[Capability.TEXT_ASSET] = Level.AUTOMATIC if parse_ok else (
        Level.WITH_WARNING if mono else Level.EXPERIMENTAL)
    levels[Capability.MONOBEHAVIOUR] = levels[Capability.TEXT_ASSET]
    levels[Capability.SERIALIZED_ASSET] = levels[Capability.TEXT_ASSET]

    levels[Capability.UNITY_UI_TEXT] = (
        Level.AUTOMATIC if (parse_ok and profile.legacy_ui)
        else Level.WITH_WARNING if parse_ok else Level.UNSUPPORTED)
    levels[Capability.TEXTMESHPRO] = (
        Level.AUTOMATIC if (parse_ok and profile.textmeshpro)
        else Level.WITH_WARNING if parse_ok else Level.UNSUPPORTED)
    levels[Capability.UNITY_LOCALIZATION] = (
        Level.WITH_WARNING if (parse_ok and profile.localization_package)
        else Level.UNSUPPORTED)
    levels[Capability.ADDRESSABLES] = (
        Level.WITH_WARNING if (parse_ok and profile.addressables)
        else Level.UNSUPPORTED)
    levels[Capability.ASSET_BUNDLE] = (
        Level.WITH_WARNING if (profile.bundles or profile.addressables)
        else Level.UNSUPPORTED)

    levels[Capability.MONO_ASSEMBLY_STRINGS] = (
        Level.EXPERIMENTAL if mono else Level.UNSUPPORTED)
    levels[Capability.IL2CPP_ANALYSIS] = (
        Level.EXPERIMENTAL if il2cpp else Level.UNSUPPORTED)
    levels[Capability.RUNTIME_HOOK] = (
        Level.WITH_WARNING if (profile.bepinex or profile.melonloader
                               or mono or il2cpp)
        else Level.UNSUPPORTED)
    levels[Capability.FONT_OVERRIDE] = (
        Level.WITH_WARNING if (parse_ok and
                               (profile.textmeshpro or profile.legacy_ui))
        else Level.UNSUPPORTED)
    return levels


def capability_summary(profile: UnityGameProfile) -> list[str]:
    """Human-readable capability lines for CLI/GUI display."""
    lines = []
    for capability, level in capabilities(profile).items():
        mark = {"automatic": "✓", "supported_with_warning": "~",
                "experimental": "?", "unsupported": "✗"}[level.value]
        lines.append(f"{mark} {capability.value}: {level.value}")
    return lines
