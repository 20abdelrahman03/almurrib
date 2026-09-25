# Unity Runtime (BepInEx + XUnity file interop)

Static patching cannot reach every game (bundles, IL2CPP, DLL text).
The runtime path leaves the game base English and serves Arabic from
files at launch — no binary patching at all.

## What Almurrib generates

`generate_xunity_bundle()` writes, from stored translations:

```text
<Bundle>/
  Translation/ar/Text/Almurrib_ar.txt   ENCODED=ENCODED pairs (TextHelper-exact)
  Config.ini                            manual-only (Endpoint= empty = offline)
  README_Almurrib_AR.txt                install steps
  Translation/ar/RedirectedResources/   translated sheet blobs (EXPERIMENTAL)
```

Pair escaping is ported from XUnity `TextHelper.cs` (v5.6.2, MIT) and
property-tested against a port of its decoder (200+ nasty strings).
Two upstream quirks are mirrored byte-for-byte: literal `//` and `%3D`
in game text can never match at runtime (verified in source, rare in
dialogue, documented — never "fixed" on our side).

## Install (user-side, game working copy only)

1. Working copy of the game (never the original).
2. Official **BepInEx 5.4.23.5** win_x64 zip into the copy (LGPL:
   user-installed, never bundled with Almurrib).
3. Official **XUnity.AutoTranslator 5.6.2** BepInEx (Mono) or
   BepInEx-IL2CPP zip. 4. Copy the bundle's `Translation/` next to the game exe.
5. Launch once (config is created), ALT+R reloads texts, ALT+T toggles.

## TextAsset redirector (bundle games without rebuilds)

XUnity's `ResourceRedirector` can dump TextAssets (`EnableDumping`) and
load overrides from `PreferredStoragePath`. Our translated full-sheet
blobs drop in there — this is how a game like Hollow Knight gets Arabic
sheets without touching its bundles. Status: EXPERIMENTAL — the exact
dump path must be confirmed from XUnity's own dump output first.

## Fonts / TMP / RTL strategy

- UGUI `OverrideFont`: any system font with Arabic glyphs.
- TMP: `FallbackFontTextMeshPro` preferred over override; TMP font asset
  bundles must be built in the **same Unity version** as the game
  (upstream constraint — a wrong-version bundle silently fails).
- RTL: XUnity substitutes text but does not shape Arabic; TMP-side RTL
  follows the RTLTMPro approach (reference only — needs the Unity
  editor, not shipped). Legacy renderers use our shared Arabic layer
  (reshaper + bidi) only where the pipeline renders, not in-game.
- Never install fonts globally; project-local only.

## Status

Bundle generation: AUTOMATED VERIFIED (parser-compatible, property
tests). In-game observation: VERIFIED on Hollow Knight (pause-menu
Arabic through hooks on pristine assets; screenshots).

## Reference: the ETR fan-translation pattern (verified by inspection)

The shipped HKEtr mod (BepInEx 6 stack) solves the same boxes problem
with three parts that mirror this document's architecture:

1. Translated sheets as `<ObjectName>.txt` XML files (LOGICAL Arabic,
   `&lt;page&gt;` entities kept) — byte-compatible with what
   `generate_redirect_sheets` emits.
2. A font AssetBundle (`etrhk`, UnityFS) carrying baked Arabic fonts.
3. A Harmony plugin (`ContainsArabic`/`FontSetterPatch`/`FontReplacer`/
   `RTLPatches`/`LoadCustomFonts`) that swaps fonts at runtime.

We copy NO code from it (unknown license, game-specific). Consequences
for Almurrib: (a) our redirect-sheet output is already interop-shaped;
(b) static font-data surgery is confirmed insufficient (engine ignores
new glyphs — baked atlas wins); the supported font paths remain
system-font `OverrideFont` (zero build) or a user-built font bundle.
Do NOT mix BepInEx 5 and BepInEx 6 installs in one game folder.
