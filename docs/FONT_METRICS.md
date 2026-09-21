# Font Metrics — Phase 2b

`FontMetrics` (`arabic/fonts.py`) measures real advance widths with
**fontTools** (MIT, pure Python — evaluated against FreeType/HarfBuzz and
chosen: no native binaries, no shaping engine needed for measurement,
PyInstaller-clean).

```python
FontMetrics("Vazirmatn-Variable.ttf", size=16)
    .width_of(text)     # sum of scaled hmtx advances
    .glyph_width(char)  # .notdef/average fallback, never 0
    .has_glyph(char)    # coverage probe (tofu detection)
    .line_height()      # hhea box, not shaping
```

Missing/invalid fonts raise (`FileNotFoundError`/`ValueError`); callers
fall back to `CharMetrics` (1 unit/char, documented limitation).
`wrap_arabic_text(..., metrics=...)` is unchanged API — measurement plugs
in with zero wrapping-logic changes.

Default font: **Vazirmatn** (`fixtures/fonts/Vazirmatn-Variable.ttf` +
`OFL.txt`, SIL OFL 1.1, from google/fonts mirror of upstream
rastikerdar/vazirmatn) — the same family proven in the real Ren'Py
rendering test. Nothing is installed into Windows; fonts stay
project-local. Each additional font needs its own license review before
bundling (see ARABIC_LAYER.md).

Measured: metric wrap ≈ CharMetrics speed class; glyph cache makes repeat
measurement ~free (see test_glossary_perf).
