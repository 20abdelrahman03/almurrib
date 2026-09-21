# Unity Support (full-stack milestone)

**Status:** structured detection · capability profiles · TextAsset +
MonoBehaviour extract · language-sheet split · sheet write-back ·
workspace/backup/rollback · XUnity runtime bundles · one-click CLI+GUI.
See `UNITY_SUPPORT_MATRIX.md` (test-filled), `UNITY_E2E.md`,
`UNITY_RUNTIME.md`, `UNITY_TOOLS.md`, `UNITY_TROUBLESHOOTING.md`.

## What works

* **Detection** (no UnityPy needed): `*_Data` layout, `globalgamemanagers`
  / `mainData` presence, `UnityFS` magic sniff, version marker when
  readable, `UnityPlayer.dll` hint. Confidence-scored with reasons.
* **Extraction:** `TextAsset` blobs (`m_Script`) + `MonoBehaviour` string
  fields via typetrees (bounded: strings over 4096 chars are data, not
  dialogue). Provenance records container/class/field for exact write-back.
* **Language sheets:** Hollow-Knight-style `TextAsset` XML
  (`<entries><entry name="KEY">text</entry></entries>`, object names like
  `EN_Banker`) splits into per-key `sheet_entry` entries; XML entities are
  unescaped to runtime values (`&lt;page&gt;` is real engine markup and is
  placeholder-protected downstream). Only the English (`EN_*`) sheet is
  extracted as source; other-language sheets are skipped (not English
  source, not translatable input). Non-sheet blobs keep whole-blob behavior.
* **Binary filter:** `TextAsset` blobs with NUL bytes or a high control-char
  ratio (fonts, raw data) are skipped — never sent to translation.
* **Rebuild:** translated copies mirror the game layout
  (`write_asset_patch`); originals untouched — delete the patch to roll
  back. Single SerializedFile assets; asset **bundles** (`.ab`) raise a
  clear error (bundle-aware rebuilds unsupported).

## What does not (and why)

* No IL2CPP/behaviour decompilation (needs Cpp2IL-class native tooling).
* No Mono/.NET assembly strings: Unity 4-era games (verified live on
  Slender 2012: detected, 331 objects parsed) keep text in DLLs, and their
  typetree-less MonoBehaviours are unreadable — reported loudly, not empty.
* No runtime hooks (BepInEx/XUnity are manual companions, not embedded).
* No bundle rebuilds. Real-game parsing is UnityPy's job (MIT, optional
  `almurrib[unity]` extra — default install and EXE stay lean).

## Verification status

 Walker/normalizer/write-back: unit-tested over duck-typed UnityPy
 surface. Detection: synthetic fixture. Real-binary parsing: UnityPy's
 responsibility.
 Sheet splitting + binary filter: unit-tested (`test_unity.py`).
 Real-game extraction VERIFIED live on Hollow Knight
 (detected Unity 0.85, 1004 assets, 4092 clean entries = 4089 sheet
 entries + 3 legit blobs, ~20s, zero NUL-bearing entries).
 Slender 2012: detected, Mono-DLL text out of scope, reported loudly.
 Sheet write-back (re-escaping keyed XML into rebuilt TextAssets) is NOT
 implemented yet — extraction-first, translation-ready; rebuild is the
 next step. Verified command: `pytest tests/unit/test_unity.py`.
