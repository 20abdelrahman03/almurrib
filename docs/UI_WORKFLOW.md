# UI Workflow (Simple default, Advanced on demand)

The GUI opens in **Simple** mode: game picker, target language, provider +
model + key, START, phase line, progress, summary. No SQLite paths, no
cache internals, no request JSON. **Advanced** (one click) reveals the full
developer surface from Phase 1/2 (database/output pickers, glossary-driven
translate, force, logs, catalog tools). All state (fields, model pool,
log text) survives mode and language switches.

## Automatic detection display

Picking a game folder auto-detects the engine and shows capabilities:

```text
Detected engine: Ren'Py
Extract: ✓ / Build: ✓ / Runtime: ✗ (unsupported)
```

Unsupported situations name the blocker and the next action instead of a
bare failure.

## Progress you can trust

Phases (`Detecting… Extracting… Translating done/total… Exporting…
Done`) plus the shared summary counters (translated/api/cache/memory,
failed, flagged, QA, glossary). Failures surface provider/model/HTTP
cause with suggestions — never a bare "finished".

## Tauri decision (recorded)

Staying with Tkinter: stdlib-only, zero-install, offline-first, working
single-file EXE today. A Tauri+React rewrite would trade all of that for
tooling weight (Node/Rust) without changing what the product can do.
Revisit only with a dedicated UI milestone and a stability budget.
