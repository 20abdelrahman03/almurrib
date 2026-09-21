# Unity E2E (what runs green)

Contract (§29): a game is "supported" only through the full chain
detect → analyze → workspace → extract → translate → QA → write-back
or runtime map → reparse → manifest → rollback check. Anything less is
labeled extraction-only.

## Automated (offline, `pytest tests/ --ignore=tests/live`)

- **Service E2E** (`test_unity_phase_e`): synthetic Mono game + fake
  UnityPy + FakeProvider through `localize_unity_game` — static strategy
  writes the patch mirror, sheet XML-escaped, manifest + hashes verify,
  originals untouched; runtime strategy emits the XUnity bundle
  (2 pairs); pre-5 layout returns an extraction-only verdict with no
  workspace left behind.
- **Sheet round-trip** (`test_unity_phase_b` + real-blob probe): one
  element swapped, reparse shows 0 disturbed neighbors (verified on
  real Hollow Knight blob data, 16 elements).
- **Stale write-back refusal**: changed source / missing key refuses
  the whole file loudly (no half-patched assets).
- **XUnity interop** (`test_unity_phase_cd`): encoder round-trips 200+
  nasty strings through a port of XUnity's own decoder rules, including
  both upstream quirks (`//`, `%3D`) mirrored exactly.
- **Safety** (phase_cd/phase_f): copy+hash manifest, tamper detection,
  existing-dest refusal, game-id stability across moves, discard removes
  the workspace and spares the original, Arabic-path workspaces.
- **Adversarial** (phase_f): corrupted asset → shaped report (no crash),
  broken sheet XML → graceful fallback, duplicate keys preserved,
  §18 Arabic fixture (9 strings) through classify/encode/sheets.

## Live (user-owned games, local only — never committed)

- **Hollow Knight**: detect AUTOMATIC; 4092 entries / ~20s; placeholder
  protection on 500 tagged samples; entity cleanup to zero leftovers.
- **Slender 2012**: pre-5 layout detected; extraction fails loudly with
  the Mono diagnostic; service verdict is extraction-only.
- **CLI**: `unity detect/inspect/tools` verified on Hollow Knight.

## Explicitly NOT verified

In-game Arabic observation (needs a user launch), real-bundle saves,
TMP/UI-text write-back, Localization-package/Addressables coverage,
IL2CPP analysis runs, Cpp2IL wiring. All labeled as such in
`docs/UNITY_SUPPORT_MATRIX.md` — extraction-only is never called support.
