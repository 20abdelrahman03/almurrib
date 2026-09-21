# RTL UI — Phase 2b foundation

The Tkinter GUI is direction-aware without being rewritten: all
widget-visible text lives in `gui/i18n.py` (`STRINGS` en/ar, `t()` with
English fallback), and `_build_ui` packs from direction tokens
(leading/trailing sides, anchors, justification swap in RTL).

* Toggle button (`عربي`/`EN`) flips `en ↔ ar`, persists `ALMURRIB_UI_LANG`
  to `.env`, and rebuilds the content frame (fields, model pool, typed
  text and log survive the rebuild).
* Source/target language dropdowns keep stable identifiers (logic
  unchanged, only chrome translates).
* Core statistics and provider messages stay English by design (universal
  units, CLI-shared, locale-free core).
* The scrolling log stays LTR (Tk Text has no real RTL layout; log lines
  are LTR-dominant `[INFO]…`). Documented limitation, not a bug.

## The three locales (see `core/overlay.py`)

```text
Almurrib UI locale   (Arabic OK here)
Game base locale     (stays English)
Displayed game text  (Arabic via overlay)
```

These are separate concepts and the architecture never conflates them.
