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
tests). In-game observation: UNVERIFIED (needs a user game + one
launch; the bundle is ready for exactly that test).
