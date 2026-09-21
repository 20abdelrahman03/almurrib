# Engine Support Matrix (honest statuses only)

| Engine | Detect | Extract | Translate | Build/Patch | Runtime | Arabic | E2E |
|---|---|---|---|---|---|---|---|
| Ren'Py (.rpy) | supported | supported | supported | supported (patch) | unsupported | verified render | verified |
| Ren'Py (.rpa v2/v3) | supported | supported | supported | via unpack+patch | unsupported | same as .rpy | synthetic-only |
| RPG Maker MV/MZ | supported | supported | supported | supported (data patch) | unsupported | via patch | verified |
| Unity | structured+capabilities | TextAsset sheets + MonoBehaviour strings | supported | static patch + XUnity runtime bundle | XUnity file interop (user-side BepInEx) | via patch/bundle | service E2E (fake) + HK live extract |
| Unreal | partial (struct) | unsupported | — | unsupported | unsupported | — | UNVERIFIED |
| Godot | partial (struct) | unsupported | — | unsupported | unsupported | — | UNVERIFIED |
| Bethesda/Skyrim | unsupported | unsupported | — | unsupported | unsupported | — | UNVERIFIED |
| VN (generic) | strategy only | unsupported | — | unsupported | unsupported | — | UNVERIFIED |

Statuses: supported = implemented + tested here; partial = documented
subset; unverified = believed possible, unproven; unsupported = evaluated,
out of scope, reason below.

## Why each unsupported stays unsupported

* **Unreal:** repak is Apache-2.0 + maintained, but Rust — no in-process
  Python story. Needs a version-matrixed native binary driven as an
  external tool (future work, interface reserved in `OverlayStrategy`).
* **Godot:** needs a gdsdecomp-class binary per Godot version; same
  external-tool shape as Unreal. Detection heuristics exist.
* **Bethesda:** Mutagen/TES5Edit/wrye-bash are .NET/manual Windows tools
  with no Python integration story; they remain manual companions.
* **VNTextPatch/Textractor/LunaTranslator:** runtime companions, not
  libraries; no embedding. Documented as manual options, not integrated.
* **UniversalInjectorFramework:** no license — ideas only, zero code copied.

## Adding an engine (the honest path)

1. `EngineInfo` row in `engine_adapters/info.py` (statuses + limitations).
2. Adapter implementing detect/extract (+ reinject); register it.
3. Synthetic or redistributable fixture + E2E test.
4. Docs row here + `docs/<ENGINE>.md` if behavior is real.
