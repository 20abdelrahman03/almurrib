# Unity Support Matrix

Filled ONLY from actual tests (prompt §36). Status words: VERIFIED /
PARTIALLY VERIFIED / EXTRACTION ONLY / EXPERIMENTAL / UNVERIFIED /
UNSUPPORTED.

| Capability | Detection | Extraction | Write-back | Runtime | Arabic | E2E |
|---|---|---|---|---|---|---|
| TextAsset (whole blob) | VERIFIED | VERIFIED (HK 4089+3) | VERIFIED (fake round-trip) | n/a | VERIFIED (pipeline) | PARTIALLY (no real-asset save — HK assets are bundles) |
| Language sheets `EN_*` | VERIFIED | VERIFIED (HK 4089 entries) | VERIFIED (real-blob round-trip, 0 neighbors disturbed) | VERIFIED (redirector blobs, EXPERIMENTAL path) | VERIFIED | PARTIALLY (save blocked by bundles) |
| MonoBehaviour fields | VERIFIED | VERIFIED (HK cells) | VERIFIED (fake round-trip) | n/a | VERIFIED | PARTIALLY (same bundle caveat) |
| Unity UI Text | VERIFIED (assembly signal) | PARTIALLY (fields surface as generic strings) | UNVERIFIED | via XUnity hooks (UNVERIFIED) | UNVERIFIED | UNVERIFIED |
| TextMeshPro | VERIFIED (assembly signal) | PARTIALLY (same as above) | UNVERIFIED | via XUnity hooks (UNVERIFIED) | UNVERIFIED | UNVERIFIED |
| Unity Localization pkg | VERIFIED (assembly signal) | UNSUPPORTED | UNSUPPORTED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
| Addressables | VERIFIED (catalog scan) | UNSUPPORTED | UNSUPPORTED | UNVERIFIED | UNVERIFIED | UNVERIFIED |
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
