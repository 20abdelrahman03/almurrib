# Unity Troubleshooting

Every failure carries its cause; this page maps symptoms to fixes.
Per-string diagnostics (§25): each entry records source text, asset /
object / field location, extraction method (`statement_kind`), glossary
state, QA flags and write-back state — inspect the DB, nothing is hidden.

## "UnityPy is not installed" (extraction)

Source installs: `uv pip install "almurrib[unity]"`. The current
`dist\Almurrib.exe` ships UnityPy INSIDE it (39.9MB) — if you still see
this error from the EXE, you are running an older build; rebuild.

## "holds N text object(s) but none are readable"

Pre-5.x Mono game (verified: Slender 2012) or Mono/.NET assembly text:
typetree-less MonoBehaviours are outside the supported subset. Verdict:
extraction-only; use the XUnity runtime path instead.

## "no Unity text extracted" + per-asset causes

Compressed/unsupported variants per asset. If SOME assets parse, you
still get entries (one hostile asset never kills the run). If NONE do,
check the listed causes — old versions and exotic compression are the
usual suspects.

## "no rebuildable Unity asset file"

Asset bundles (`.ab`) need bundle-aware rebuilds: UnityPy's `save()`
needs a packer argument there. Use the external UABEA v8 path
(see `docs/UNITY_TOOLS.md`), or the runtime bundle (no rebuild needed).

## Sheet write-back refused: "key gone" / "source changed"

Stale translation (game updated between extract and export). Re-extract,
re-translate, retry. The file is refused as a whole — no half-patched
assets, by design.

## Mixed whole-blob and element replacements

Internal inconsistency (same object addressed both ways). Re-extract;
if it persists, file a bug with the asset name + object.

## Game launches but English remains (runtime path)

1. ALT+R (reload files). 2. Check `Translation/ar/Text/*.txt` is next
   to the exe. 3. Enable disabled frameworks in Config.ini (IMGUI/TextMesh
   are off by default upstream). 4. Texts over 2500 chars are ignored
   upstream (our bundle reports skipped_long). 5. `//` or `%3D` texts
   never match (upstream quirk, documented).

## Arabic shows as boxes / disconnected letters

Font lacks Arabic glyphs: set `FallbackFontTextMeshPro` (TMP) or
`OverrideFont` (UGUI) in Config.ini. TMP bundles must match the game's
Unity version. RTL shaping is TMP-side; see `docs/UNITY_RUNTIME.md`.

## Spaces / Arabic paths

Supported and tested (workspace + manifest are Unicode paths). If the
GAME itself fails on such paths, keep the working copy on an ASCII path
and note it in the report.

## Rollback

Delete the workspace (`*_ar_work/`) — originals were never written.
`verify_originals` (run automatically) proves baseline hashes match.
