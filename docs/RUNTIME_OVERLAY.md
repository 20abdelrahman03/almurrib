# Runtime Overlay (Phase 3 capabilities, honest scope)

Product rule: **game base stays English; the player sees Arabic.**
`core/overlay.py` represents this (`OverlayPlan`: base/displayed locale,
strategy, active flag) without implementing injection.

## Strategies (protocol, not product — except the first)

| Strategy | Meaning | Status |
|---|---|---|
| `LANGUAGE_DIR` | engine loads `tl/<lang>/` natively | **working** (Ren'Py manual test, user-verified render) |
| `LOOKUP_OVERRIDE` | engine string-lookup hook | interface only |
| `RESOURCE_PATCH` | patched bundles on disk | interface only (Unity/RPGM rebuilds are static patches, adjacent) |
| `INTERCEPTION` | runtime text hook | interface only (no BepInEx/UE4SS/VNTextPatch embedding) |

## Static patch vs runtime (what ships today)

Ren'Py and RPG Maker localize by **patch directory** (originals untouched,
delete-to-rollback). Unity rebuilds translated asset copies (same rule).
These are build-time overlays: the base game files never change, the
localized files take precedence at load. No process injection, no DLLs,
no hooks — deliberately.

## Adaptive observation (designed, minimal)

The architecture permits opt-in local collection (untranslated text seen
at runtime → stored → translated later → shown next run) through the same
entry/TM pipeline. Not implemented (needs a runtime per engine = Phase 3
proper). No automatic upload, ever.

## What each engine answers today

Ren'Py (`adapter.overlay_plan()`): `LANGUAGE_DIR` with `tl/<lang>/`.
Others: extend `overlay_plan()` when their strategy becomes real.
