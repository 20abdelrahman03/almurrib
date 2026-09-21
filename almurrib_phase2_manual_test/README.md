# Station 7 — Phase 2 manual acceptance fixture

A dense little English browser talking-game (72 nodes, 12 choice points,
97 strings) plus real Almurrib glossary/QA fixtures and a deterministic
localization loop. Zero backend, zero internet, zero money for the
deterministic path.

```text
almurrib_phase2_manual_test/
  browser/          index.html + styles.css + app.js (EN/AR/overlay + debug)
  game_data/        dialogue.json + glossary.json + qa_cases.json
  tools/            json_to_rpy.py + strings_to_ar_json.py (TEST HARNESS)
  rpy/              generated Ren'Py mirror (regenerable, do not hand-edit)
  output/           dialogue_ar.json + almurrib_out/ (generated)
  docs/             PHASE2_MANUAL_TEST.md (the click-by-click procedure)
  START_GAME.bat    local static server + browser (ASCII-only, codepage-safe)
```

Start here: `docs/PHASE2_MANUAL_TEST.md`.
