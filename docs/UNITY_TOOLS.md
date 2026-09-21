# Unity Tools — Research & Integration Decisions

Researched 2026-09-21 via GitHub MCP (live API: repo metadata, LICENSE
contents, latest releases). Rule: integrate only with a clear engineering
purpose; never vendor without license justification.

## Accepted

### K0lb3/UnityPy — integrated dependency (already)
- MIT · Python · active (pushed 2026-08, ~1.4k stars) · venv has 1.25.3.
- Purpose: asset parse/extract for TextAsset + MonoBehaviour typetrees.
- Integration: `almurrib[unity]` optional extra (keeps base install + EXE lean).
- Result: already the parsing backbone; stays.

### nesrak1/UABEA — optional external tool
- MIT (verified `license` file) · C# · active Sept 2026 · 2.4k stars.
- Last classic release **v8** (2024-11, win/mac zips; needs .NET 6 Runtime);
  author moved to **UABEANext** (rewrite, docking + multi-bundle).
- Purpose: AssetBundle inspect/extract/modify/rebuild where UnityPy cannot.
- Integration: **external subprocess/GUI companion, never vendored**
  (C# binary, user-downloaded, recorded in tool manager with version/hash).
- Result: accepted as the bundle rebuild path.

### bbepis/XUnity.AutoTranslator — external runtime + file-format interop
- MIT (verified) · C# · active, **v5.6.2 (2026-09-10)** · 3.4k stars.
- Ships BepInEx + **IL2CPP** + MelonMod builds, `ResourceRedirector`,
  `OverrideFontTextMeshPro` (incl. system-name font override).
- Purpose: runtime translation overlay for games where static patching
  is impossible (IL2CPP, DLL text).
- Integration: **we generate its translation files** (tab-delimited
  `source=translation` mapping) from our pipeline — pure file-format
  interop, zero code copied. BepInEx install stays user-side.
- Result: accepted as THE runtime strategy.

### BepInEx/BepInEx — external runtime component only
- **LGPL-2.1** (verified) — copyleft library license.
- Active (v5.4.23.5 LTS Feb 2026; v6 on master) · 8.6k stars ·
  win_x64 zip ~640KB, 1.8M downloads.
- Purpose: plugin host that loads XUnity inside the game process.
- Integration: **never vendored, never linked, never bundled in EXE**.
  User installs official release into the game's working copy; our tool
  manager only records presence/version. LGPL-safe (separate program).
- Result: accepted as user-side prerequisite, documented as such.

## Dev / reference only

- **nesrak1/UABEANext** — rewrite for multi-bundle research; watch, no integration yet.
- **nesrak1/AssetsTools.NET** — MIT, active, but C# library with no
  Python binding; UABEA covers the CLI need. Reference for format knowledge.
- **SamboyCoding/Cpp2IL** — MIT, code active Sept 2026, but **binary
  release stale (2022.0.7)**. Optional external CLI for IL2CPP *analysis*
  (detection-grade), never for binary patching. Honest limits documented.
- **xSh4r103/AnyFontUnity** — MIT but newborn (Sept 2026, 3 stars),
  MelonLoader-based font injector. Too immature; watch only.
- **pnarimani/RTLTMPro** — MIT, active Sept 2026, 720 stars. RTL plugin
  for TextMeshPro (Arabic/Persian). Needs the Unity editor to integrate,
  so it informs our **font/RTL strategy doc**, not shipped code.
- **Veydzher/i2loc-manager** — MIT, Python/PySide6 manager for I2
  Localization dumps via UABEA. Reference for I2 table handling (§9E).

## Rejected

- **Dean20030514/game-translator-releases** (multi-engine LLM game
  translator, Ren'Py/RPGM/Unity) — releases only, **source private**.
  No license, nothing to reuse. Market-space reference only.
- **SeriousCache/UABE** — archived, author points to UABEA. Rejected.
- Random UABEA Android ports / zero-star forks — no engineering value.

## Architecture consequences

1. Python core stays authoritative: UnityPy (parse) + our pipeline
   (glossary/QA/TM/provenance) + generated artifacts.
2. C# world stays **outside our process**: UABEA (bundles), BepInEx +
   XUnity (runtime) are user-side tools we *orchestrate and verify*,
   never embed — this keeps licenses clean (esp. LGPL) and the EXE lean.
3. Runtime translation = our DB → XUnity-format file + Arabic font
   strategy (XUnity TMP font override + RTLTMPro knowledge).
4. Static patching = working copy + UnityPy write-back (single assets)
   + UABEA-side bundles, all behind backup/manifest/rollback.
