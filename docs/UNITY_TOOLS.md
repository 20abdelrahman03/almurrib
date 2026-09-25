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

## Accepted (super-refactor delta, researched 2026-09-22)

### AssetRipper/AssetRipper — optional external extraction fallback
- **GPL-3.0** (verified `LICENSE.md`) · C# · very active (8.4k stars,
  commits current week). Successor of the archived AssetStudio.
- Exports whole games to Unity-project format (TextAssets as files,
  MonoBehaviours as YAML) — a viable extraction fallback when UnityPy
  cannot parse an asset. GUI app; headless use via the
  **MeikoMei16/AssetRipper-CLI** fork (active 2026, profile-based export).
- Integration: **external program only, never vendored, never linked**
  (GPL boundary respected: we read its *exported data files*, which are
  the game's own data, not its code). Tool manager records presence.
- Result: accepted as the documented fallback behind UnityPy.

### Perfare/Il2CppDumper — optional external IL2CPP analysis
- **MIT** (verified `LICENSE`) · C# · very active (9.4k stars).
- Console builds dump `il2cpp_data/Metadata/global-metadata.dat` into
  `dump.cs` + script JSON (types, fields, metadata string table) —
  the only safe static window into IL2CPP text discovery.
- Integration: **external CLI** (`Il2CppDumper.exe game.exe`),
  user-downloaded; we parse its *output files*, never its code.
  Never for binary patching — analysis only.
- Result: accepted for the IL2CPP_ANALYSIS capability.

### BepInEx-bundled stack — no separate integration
- **HarmonyX, Unity Doorstop, Il2CppInterop (BepInEx/Il2CppInterop,
  active Sept 2026)**: all ship INSIDE the BepInEx 5/6 distributions
  we already register. Registering them separately would double-count
  one install. The tool manager notes them as BepInEx components.

### FairyGUI — covered via XUnity, no new work
- **fairygui/FairyGUI-unity** (active, 3k stars) is a UI framework games
  are built with, not a translation tool. XUnity already hooks it
  (listed in its text frameworks), so our runtime path covers
  FairyGUI games through file interop. No integration needed.

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
