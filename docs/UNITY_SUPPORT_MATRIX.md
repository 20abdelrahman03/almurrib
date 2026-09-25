# Unity Support Matrix

Filled ONLY from actual tests (prompt §36). Status words: VERIFIED /
PARTIALLY VERIFIED / EXTRACTION ONLY / EXPERIMENTAL / UNVERIFIED /
UNSUPPORTED.

| Capability | Detection | Extraction | Write-back | Runtime | Arabic | E2E |
|---|---|---|---|---|---|---|
| TextAsset (whole blob) | VERIFIED | VERIFIED (HK 4089+3) | VERIFIED (fake round-trip) | n/a | VERIFIED (pipeline) | PARTIALLY (no real-asset save — HK assets are bundles) |
| Language sheets `EN_*` | VERIFIED | VERIFIED (HK 4089 entries) | VERIFIED (real-blob round-trip, 0 neighbors disturbed) | VERIFIED (redirector blobs, EXPERIMENTAL path) | VERIFIED | VERIFIED on real Hollow Knight (22 elements written, reparse clean, census identical, game launches; bundle inputs refused) |
| MonoBehaviour fields | VERIFIED | VERIFIED (HK cells) | VERIFIED (fake round-trip) | n/a | VERIFIED | VERIFIED on real Hollow Knight (22 elements written, reparse clean, census identical, game launches; bundle inputs refused) |
| Unity UI Text | VERIFIED (assembly signal) | PARTIAL (generic leaves + ui_text field tags) | UNVERIFIED | via XUnity hooks (UNVERIFIED) | UNVERIFIED | UNVERIFIED |
| TextMeshPro | VERIFIED (assembly signal) | PARTIAL (generic leaves + ui_text field tags) | UNVERIFIED | via XUnity hooks (UNVERIFIED) | UNVERIFIED | UNVERIFIED |
| Unity Localization pkg | VERIFIED (assembly signal) | UNSUPPORTED | UNSUPPORTED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| Addressables | VERIFIED (catalog JSON parsed: bundle refs) | UNSUPPORTED | UNSUPPORTED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| AssetBundle `.ab` | VERIFIED (file scan) | PARTIALLY (UnityPy reads; inspect reports) | UNSUPPORTED in-process (external UABEA path documented) | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| Mono DLL strings | VERIFIED (Slender: loud diagnostic) | UNSUPPORTED | UNSUPPORTED (never corrupt assemblies) | via XUnity (UNVERIFIED) | UNVERIFIED | UNVERIFIED |
| IL2CPP | VERIFIED (GameAssembly signal) | UNSUPPORTED | UNSUPPORTED | via XUnity IL2CPP build (UNVERIFIED) | UNVERIFIED | UNVERIFIED |
| BepInEx present | VERIFIED (dir scan) | n/a | n/a | UNVERIFIED (user-side) | n/a | UNVERIFIED |
| Font override | signal only | n/a | n/a | UNVERIFIED (TMP same-version caveat) | UNVERIFIED | UNVERIFIED |

## Era calibration (real games, local)

- **Hollow Knight** (Mono, x64, 1004 assets): profile AUTOMATIC on parse
  caps; 4092 entries extracted in ~20s; sheet round-trip verified on
  real blob data. Static save untested on its bundles (honest limit).
- **Slender 2012** (Mono, x86, pre-5 `mainData` layout): profile has zero
  AUTOMATIC; extraction fails loudly with the Mono-typetree diagnostic
  (verified). Extraction-only verdict end-to-end.

## Performance (measured 2026-09-21)

- Analysis (1004-asset game on disk): **0.15s** (stdlib only).
- Extraction (Hollow Knight, 4092 entries): **~20s** (UnityPy-bound).
- Classification: **250k+ strings/s** (4092 in 0.02s).
- Workspace copy+hash: **~1s per 500 small files** (I/O bound).
- Memory: extraction holds one asset in UnityPy at a time plus the
  entry list (no whole-project preload beyond that).

## Super-refactor additions (all VERIFIED by tests unless noted)

| Capability | Status |
|---|---|
| Dedup fan-out (canonical source + occurrences) | VERIFIED (37x1-call test, context-split test) |
| Canary gate (3 forced entries, auto over 100 pending) | VERIFIED |
| Acceptance progress + breaker + token rule | VERIFIED (incident suite) |
| Per-chunk persist + stop/pause/resume | VERIFIED (stop/pause/crash/resume tests) |
| Atomic write-back + reparse validation | VERIFIED (refusal deletes staging) |
| Strategy engine with reasons | VERIFIED (IL2CPP/bundle/static/weak cases) |
| Per-entry diagnostics | VERIFIED (explain command) |
| JSON + HTML localization reports | VERIFIED (service writes both) |
| Rollback (verify originals + discard) | VERIFIED |
| Addressables catalog JSON parsing | VERIFIED (synthetic + malformed) |
| Patch path-traversal refusal | VERIFIED (section 26) |
| In-game Arabic observation | UNVERIFIED (needs user launch) |
| Real-bundle saves | UNVERIFIED (no test game with bundles) |

## Field test 2026-09-22 (Hollow Knight test copy, user-owned)

- Canary (production CohereProvider, command-a-plus-05-2026): 3/3 PASS.
- Slice 1 (EN_StagMenu, 14 dialogue lines): 14/14 accepted, written,
  reparsed 14/14 Arabic, object census 26536 == 26536.
- Slice 2 (EN_MainMenu, 8 menu items): 8/8 accepted, written, reparsed.
- Game launched with patched resources.assets: healthy boot (Player.log),
  no asset errors, main menu shows shaped Arabic
  (Start/Options/Extras/Quit), untranslated keys stay English.
- Bugs found live: dict-shaped file.objects iteration, sibling-sheet key
  collision, Windows file lock on reparse-validate — all fixed with
  regression tests (test_unity_super.py).
- Original game verified untouched (SHA256); test copy at E:/HK_Test.

## Field test 2: fonts + runtime (2026-09-22, test copy, user-owned game)

- Embedded fonts (4 total: Perpetua, NotoSerifCJKsc, TrajanPro x2):
  0/256 basic Arabic, 0 presentation forms (fontTools-measured).
  Fallback chains end at Noto CJK (also 0 Arabic).
- Menu/prompt Arabic renders (OS-fallback path); intro/autosave serif
  shows tofu -> per-element font dependence, proven by screenshots.
- Static m_FontData swap (Vazirmatn subset, OFL) technically succeeds
  (asset rebuilds, game boots, Latin intact) but does NOT enable new
  glyphs at runtime (baked atlas wins). Dead end recorded with evidence.
- Runtime overlay VERIFIED in-game: BepInEx 5.4.23.5 (sha256-verified) +
  XUnity 5.6.2, manual-only config (Endpoint empty, Language ar,
  FromLanguage en), 22 Almurrib pairs under BepInEx/Translation/ar/Text.
  Pause menu shows runtime Arabic on PRISTINE assets.
- XUnity quirk found live: ALT+R reload crashes file loading unless an
  (even empty) _AutoGeneratedTranslations.txt exists -> our generator
  now always ships it (regression-tested).
- Translation dir that XUnity actually reads: BepInEx/Translation/
  (not game root). Config merged into BepInEx/config/AutoTranslatorConfig.ini.

## Font verdict (field-proven 2026-09-22, screenshots)

- Embedded fonts (Perpetua, NotoSerifCJKsc, TrajanPro x2): 0/256 Arabic,
  0 presentation forms (fontTools-measured). Fallback chains end at
  Noto CJK (also 0). So SOME elements can never render Arabic statically.
- Menu/prompt/profile/slot UI: Arabic renders (system-fallback path).
- Serif display elements (intro poem, autosave warning): tofu boxes.
- Static m_FontData swap (Vazirmatn/OFL subset, bytes verified on disk):
  rebuilds + boots + Latin intact, but engine does NOT rasterize new
  glyphs (baked atlas wins). Dead end recorded with evidence.
- Runtime OverrideFont=Arial configured in the full workspace
  (BepInEx 5.4.23.5 + XUnity 5.6.2, manual-only, 3280 pairs under
  BepInEx/Translation/ar/Text). Autosave-screen verdict pending a
  well-timed capture (2-4s window at boot).
- Full-workspace state (Hollow Knight_ar_full): 3744 static entries
  patched + runtime stack installed + reports. Playable Arabic build.
