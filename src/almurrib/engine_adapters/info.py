"""Engine capability model (honest, data-driven).

Every engine Almurrib knows about is described once here: what works,
what is partial, what is unsupported — no guessing from the UI side.
Adapters implement behavior; this table declares it. Statuses:

* supported   — implemented + tested (unit/integration/E2E as noted)
* partial     — works for a documented subset
* experimental— implemented, thinly verified
* unverified  — believed possible, not proven here
* unsupported — evaluated and out of scope (reason recorded)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EngineInfo:
    id: str
    display_name: str
    detect: str = "unsupported"
    extract: str = "unsupported"
    export_build: str = "unsupported"
    runtime: str = "unsupported"
    arabic_fonts: str = "unsupported"
    formats: tuple[str, ...] = ()
    limitations: tuple[str, str, ...] = ()
    notes: str = ""


ENGINES: dict[str, EngineInfo] = {
    "renpy": EngineInfo(
        id="renpy",
        display_name="Ren'Py",
        detect="supported",
        extract="supported",
        export_build="supported",
        runtime="unsupported",
        arabic_fonts="supported",
        formats=(".rpy", ".rpa v2/v3 (safe reader, temp-unpack)"),
        limitations=(
            "screen-language UI strings are not extracted",
            "dialogue translate-blocks need engine ids (string translation used)",
        ),
        notes="String-translation patch; originals untouched.",
    ),
    "rpgmaker": EngineInfo(
        id="rpgmaker",
        display_name="RPG Maker MV/MZ",
        detect="supported",
        extract="supported",
        export_build="supported",
        runtime="unsupported",
        arabic_fonts="partial",
        formats=(".json data files",),
        limitations=(
            "script (JS plugin) strings are not extracted",
            "tileset/animation metadata names are skipped",
        ),
        notes="Translated data files mirror the game layout into a patch dir.",
    ),
    "unity": EngineInfo(
        id="unity",
        display_name="Unity",
        detect="supported",
        extract="partial",
        export_build="partial",
        runtime="unsupported",
        arabic_fonts="partial",
        formats=("UnityFS .assets",),
        limitations=(
            "TextAsset + string fields only; no IL2CPP/behaviour decompile",
            "synthetic-fixture E2E (no redistributable real game in repo)",
        ),
        notes="UnityPy-backed; working-copy patching with rollback notes.",
    ),
    "unreal": EngineInfo(
        id="unreal",
        display_name="Unreal Engine",
        detect="partial",
        limitations=("needs repak-class native tooling per engine version",),
        notes="Evaluated: repak is Apache-2.0 but Rust (no in-process "
        "Python story); extraction/patch deferred, documented honestly.",
    ),
    "godot": EngineInfo(
        id="godot",
        display_name="Godot",
        detect="partial",
        limitations=("needs gdsdecomp-class binary per Godot version",),
        notes="Evaluated; unpacking deferred, documented honestly.",
    ),
}


def get_engine_info(engine_id: str) -> EngineInfo | None:
    return ENGINES.get(engine_id)


def capability_summary() -> list[tuple[str, str, str, str, str]]:
    """Rows for docs/UI: (display, detect, extract, build, runtime)."""
    return sorted(
        ((info.display_name, info.detect, info.extract, info.export_build,
          info.runtime)
         for info in ENGINES.values()),
        key=lambda row: row[0].lower(),
    )
