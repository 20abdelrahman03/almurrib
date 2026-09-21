# Unity Full-Stack Milestone — Build Plan

Source: `almurrib_unity_fullstack_e2e_prompt(1).md` (§1–§39).
Research: `docs/UNITY_TOOLS.md` (GitHub MCP, 2026-09-21 — all 7 arsenal
repos + RTLTMPro + i2loc-manager audited, licenses verified from source).

## Architecture (no second Unity stack)

```text
analysis.py    structured profile + capability levels (NEW)
classify.py    string candidate verdicts (NEW)
unityfs.py     parse + TextAsset/MonoBehaviour write-back (EXTEND: sheets)
adapter.py     detect/extract (EXTEND: classification tags)
workspace.py   working copy + manifest + rollback (NEW)
tools.py       external-tool registry (NEW, researched versions)
runtime.py     XUnity bundle generator, exact TextHelper escaping (NEW)
reinject.py    route sheet entries to element write-back (EXTEND)
cli            `almurrib unity <detect|inspect|extract|localize>` (NEW group)
gui            one-click Unity panel on shared service (NEW tab)
```

Core stays authoritative: glossary, QA, TM/provenance, Arabic layer —
Unity code is only the engine bridge.

## Phase A — Know the game (§7, §8, §10) [first]

- `UnityGameProfile`: version, backend (Mono/IL2CPP), arch, Managed
  assemblies, StreamingAssets/Resources, bundles, Addressables markers,
  Localization-package markers, TMP/UI assemblies, BepInEx/MelonLoader
  presence — all stdlib (PE-machine read, name scans), no UnityPy needed.
- `Capability` enum (12 from prompt) × level
  (AUTOMATIC / WITH_WARNING / EXPERIMENTAL / UNSUPPORTED).
- `classify_candidate`: TECHNICAL (GUID/path/URL/class/shader/keys/IDs)
  vs LIKELY vs POSSIBLY + reason; recorded as tags, never silent drops.

## Phase B — Write-back (§9A/B, §12, §13) [the main requirement]

- `replace_sheet_elements(blob, {key: new})`: regex element swap with
  XML re-escape; pure + unit-tested; reinject routes `entry[K]` fields.
- Round-trip contract per type: parse → change one string → write →
  reparse → verify neighbors (fakes + synthetic where Unity-authoring
  is impossible; labeled honestly).
- Bundles `.ab`: inspect via UnityPy (list/count) + precise diagnostic;
  rebuild via external UABEA only (never fake UnityPy bundle saves).

## Phase C — Safety + services (§2, §22, §23, §26)

- `prepare_workspace`: disk-space check → copy → sha256 manifest →
  localized copy; `rollback` restores hashes (tested).
- `localize_unity_game()`: detect→analyze→workspace→extract→(shared
  translate+QA)→strategy→patch/runtime bundle→validate→report.
- Tool registry: UnityPy/UABEA/Cpp2IL/BepInEx/XUnity with researched
  versions, install probes, license flags (LGPL: external-only).

## Phase D — Runtime path (§16, §17)

- XUnity bundle: `Translation\ar\Text\Almurrib_ar.txt` with **exact**
  `TextHelper` escaping (ported + verified by Python port of the C#
  decoder, property-tested), `Config.ini` (Endpoint empty = manual-only
  offline lookup, Language=ar, FromLanguage=en, frameworks on),
  install guide (user installs BepInEx+XUnity, LGPL-safe).
- TextAsset-redirector variant: translated sheets (full XML blobs) for
  `RedirectedResources` — solves bundle games without rebuilds.
- Font strategy doc: TMP fallback/override (same-Unity-version caveat),
  RTLTMPro knowledge, system-font option (#854); no global installs.

## Phase E — Surface (§24, §33) + honesty (§25, §27, §29)

- CLI group + GUI one-click panel (capability checklist, progress,
  Launch/Rollback buttons) on the shared service.
- Per-string diagnostics (source/location/method/QA/write-back state).
- Support matrix filled ONLY from actual tests.

## Phase F — Prove it (§18, §30, §31, §32, §34–§37)

- Arabic E2E fixture strings through pipeline; adversarial battery;
  perf on synthetic scales (1k/10k/50k assets); full refactor;
  EXE from another cwd; docs + matrix; §38 final report in chat.
- Absolute: no auto-commit; extraction-only never labeled supported.
