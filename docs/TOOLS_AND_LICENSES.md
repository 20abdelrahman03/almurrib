# Tools & Licenses (audited 2026-09)

Every external project evaluated for Phase 3, with verdict and reason.
Nothing here is vendored except where stated; no-license sources were
never copied.

## Integrated (dependency, lazy/optional where heavy)

| Project | Version | License | Method | Notes |
|---|---|---|---|---|
| UnityPy (K0lb3) | 1.25.3 | MIT | optional `almurrib[unity]` | asset parse/rebuild; heavy transitive stack stays out of default+EXE |
| argostranslate | 1.11.0 | MIT | optional `almurrib[offline]` | offline NMT; torch stack stays out; models download on explicit command |

## Implemented in-house (no dependency needed)

* Ren'Py RPA v2/v3 reader (own code; unrpa evaluated: GPL-3.0 combinable
  but rejected — raw-pickle RCE on untrusted archives; ours uses a
  restricted unpickler + traversal guards).
* llama.cpp lifecycle helper (server is user-provided; stdlib only).

## Evaluated, not integrated (with reason)

| Project | License | Verdict |
|---|---|---|
| repak (trumank) | Apache-2.0 | external-binary path (Rust, no in-process story) |
| gdsdecomp | ? (repo moved/404) | deferred; needs versioned binary |
| VNTextPatch | ? (repo 404) | strategy reference only |
| Textractor/LunaTranslator/Translumo/MORT/SExtractor | mixed | runtime companions, not libraries |
| BepInEx / XUnity.AutoTranslator / UE4SS | mixed | manual companions; no embedding |
| UABEA / AssetsTools.NET / Cpp2IL / UAssetAPI | mixed | .NET native tools; external-manual path |
| CTranslate2 / LLamaSharp / LibreTranslate | mixed | covered by Argos + llama-server paths |
| yexi-by/att | ? | no value over direct JSON handling |
| AnyFontUnity | ? | reference for font strategy |
| UniversalInjectorFramework | **none** | ideas only, zero code |
| Velopack | Apache-2.0 | portable-zip now; Velopack path documented, not adopted |
| SignPath | commercial | not performed (never claimed) |

## Runtime dependencies (current truth)

stdlib + `arabic-reshaper` (MIT) + `python-bidi` (LGPL-3.0) + `fonttools`
(MIT). Optionals: `unity`, `offline`. Dev: pytest, pyinstaller. See
`THIRD_PARTY_NOTICES.md` + `pyproject.toml`.
