"""External Unity tool registry (§26 of the milestone).

Every entry records the researched version, license and integration
method (see docs/UNITY_TOOLS.md). Nothing here is vendored or
auto-downloaded: Almurrib only PROBES for tools and tells the user
exactly what to install from the official source.

License rule encoded below: LGPL tools (BepInEx) are strictly
``external`` — never bundled, never linked, never shipped in the EXE.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolInfo:
    key: str
    name: str
    repo: str
    version: str          # researched version (see UNITY_TOOLS.md)
    license: str
    method: str           # dependency | external | reference
    purpose: str
    install_hint: str
    url: str


REGISTRY: tuple[ToolInfo, ...] = (
    ToolInfo("unitypy", "UnityPy", "K0lb3/UnityPy", "1.25.3", "MIT",
             "dependency", "asset parsing (TextAsset/MonoBehaviour)",
             'uv pip install "almurrib[unity]"',
             "https://github.com/K0lb3/UnityPy"),
    ToolInfo("uabea", "UABEA", "nesrak1/UABEA", "v8", "MIT", "external",
             "AssetBundle inspect/extract/modify/rebuild",
             "download uabea-windows.zip from Releases (.NET 6 Runtime needed)",
             "https://github.com/nesrak1/UABEA/releases/tag/v8"),
    ToolInfo("cpp2il", "Cpp2IL", "SamboyCoding/Cpp2IL", "dev-branch "
             "(binary release stale: 2022.0.7)", "MIT", "external",
             "IL2CPP analysis only (detection-grade, never binary patching)",
             "build from source or use the 2022.0.7 binary with care",
             "https://github.com/SamboyCoding/Cpp2IL"),
    ToolInfo("bepinex", "BepInEx", "BepInEx/BepInEx", "5.4.23.5 LTS",
             "LGPL-2.1 (external-only: never bundled/linked)", "external",
             "plugin host that loads the runtime translator in-game",
             "extract the official win_x64 zip into the game folder",
             "https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.5"),
    ToolInfo("xunity", "XUnity.AutoTranslator", "bbepis/XUnity.AutoTranslator",
             "5.6.2", "MIT", "external",
             "runtime translation overlay (reads our generated files)",
             "extract the BepInEx (or IL2CPP) zip into the game folder",
             "https://github.com/bbepis/XUnity.AutoTranslator/releases/tag/v5.6.2"),
    ToolInfo("assetripper", "AssetRipper", "AssetRipper/AssetRipper",
             "rolling master", "GPL-3.0 (external-only: never vendored/linked)",
             "external",
             "extraction fallback: exports games to Unity-project format "
             "(TextAssets as files, behaviours as YAML)",
             "download release or AssetRipper-CLI fork; point tool at game",
             "https://github.com/AssetRipper/AssetRipper"),
    ToolInfo("il2cppdumper", "Il2CppDumper", "Perfare/Il2CppDumper",
             "rolling master", "MIT", "external",
             "IL2CPP static analysis only: dump.cs + metadata JSON "
             "(never binary patching)",
             "run Il2CppDumper.exe on the game exe + metadata file",
             "https://github.com/Perfare/Il2CppDumper"),
    ToolInfo("anyfontunity", "AnyFontUnity", "xSh4r103/AnyFontUnity",
             "2026-09 (immature)", "MIT", "reference",
             "font-injection ideas only — too new to depend on",
             "watch, do not integrate yet",
             "https://github.com/xSh4r103/AnyFontUnity"),
    ToolInfo("rtltmpro", "RTLTMPro", "pnarimani/RTLTMPro", "master",
             "MIT", "reference",
             "TMP Arabic/Persian RTL strategy knowledge",
             "needs the Unity editor; strategy doc only",
             "https://github.com/pnarimani/RTLTMPro"),
)


@dataclass
class ToolStatus:
    key: str
    installed: bool
    detail: str = ""


def probe(key: str, game_dir: Path | None = None) -> ToolStatus:
    """Check whether one tool is available (never installs anything)."""
    if key == "unitypy":
        try:
            import UnityPy

            return ToolStatus(key, True,
                              f"UnityPy {getattr(UnityPy, '__version__', '?')}")
        except ImportError:
            return ToolStatus(key, False, "pip package missing")
    if key == "uabea":
        found = shutil.which("UABEA") or _which_any(
            ("UABEAvalonia.exe", "UABEA.exe"))
        return ToolStatus(key, bool(found), found or "not on PATH")
    if key == "cpp2il":
        found = shutil.which("Cpp2IL") or shutil.which("Cpp2IL.exe")
        return ToolStatus(key, bool(found), found or "not on PATH")
    if key == "assetripper":
        found = _which_any(("AssetRipper.exe", "AssetRipper",
                             "AssetRipper.CLI.exe"))
        return ToolStatus(key, bool(found), found or "not on PATH")
    if key == "il2cppdumper":
        found = _which_any(("Il2CppDumper.exe", "Il2CppDumper"))
        return ToolStatus(key, bool(found), found or "not on PATH")
    if key == "bepinex":
        root = Path(game_dir) if game_dir else None
        present = root is not None and (
            (root / "BepInEx").is_dir()
            or list(root.glob("doorstop_config.ini")))
        return ToolStatus(key, bool(present),
                          "BepInEx/ in game folder" if present
                          else "not installed in this game")
    if key == "xunity":
        root = Path(game_dir) if game_dir else None
        present = root is not None and (
            (root / "BepInEx" / "plugins" / "XUnity.AutoTranslator").is_dir()
            or (root / "AutoTranslator").is_dir())
        return ToolStatus(key, bool(present),
                          "XUnity plugin dir present" if present
                          else "not installed in this game")
    return ToolStatus(key, False, f"unknown tool '{key}'")


def _which_any(names: tuple[str, ...]) -> str:
    for name in names:
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            candidate = Path(directory) / name
            if candidate.is_file():
                return str(candidate)
    return ""


def status_table(game_dir: Path | None = None) -> list[str]:
    """Display lines for CLI/GUI diagnostics."""
    lines = []
    for tool in REGISTRY:
        status = probe(tool.key, game_dir)
        mark = "✓" if status.installed else "·"
        lines.append(f"{mark} {tool.name} {tool.version} "
                     f"[{tool.method}] — {status.detail}")
    return lines
