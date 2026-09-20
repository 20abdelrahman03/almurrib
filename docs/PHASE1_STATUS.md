# Phase 1 Status — First 50% Complete

## ✅ What works

```text
✅ Project structure with clean core / adapter / storage / cli boundaries
✅ Core localization model (normalized, serializable, deterministic ids)
✅ SQLite persistence with schema migrations (repository pattern, no scattered SQL)
✅ Deterministic translation cache (in-memory + SQLite backends)
✅ Pipeline abstraction: Detect → Extract → Normalize → (Translate*) → (Validate*) → Export
   * interfaces + no-op defaults now; real implementations in Phase 1b/2
✅ Ren'Py detection (game/ dir + .rpy scripts heuristics)
✅ Ren'Py extraction: say statements, menu choices, translate-strings pairs
✅ Source references preserved (file + line + statement kind) for later reinjection
✅ JSON export of normalized entries for inspection/testing
✅ CLI: detect / extract / inspect / db
✅ Deterministic tiny Ren'Py fixture
✅ Tests pass (31 tests: model, storage, cache, pipeline, parser, adapter, CLI)
```

## ⏳ Intentionally not done (remaining 50% of Phase 1)

```text
⏳ llama.cpp integration (local inference backend)
⏳ Qwen 2.5 translation provider wired into TranslateStage
⏳ Translation execution with cache read/write in the live pipeline
⏳ Ren'Py reinjection (writing translations back as a `translate arabic` file)
⏳ Compiled .rpyc support (via unrpyc-style tooling, as an adapter concern)
⏳ Translation memory reuse across projects
⏳ Real-game end-to-end localization walkthrough
```

Explicitly deferred to later phases: Arabic reshaping/BiDi/fonts, QA rules,
glossary, other engines, runtime injection, TMX/XLIFF sharing, UI.

## Next step (second 50% of Phase 1) — not implemented here

1. **Provider interface**: formalize a `TranslationProvider` protocol
   (name, capabilities, `translate_batch(entries) -> entries`).
2. **llama.cpp adapter**: local provider via llama.cpp server/binary,
   running Qwen 2.5; cache-backed batch translation in `TranslateStage`.
3. **Ren'Py reinjection**: generate a `game/tl/arabic/*.rpy` translation
   file from stored entries using the preserved `SourceRef`s; re-run game
   to validate.
4. **End-to-end**: localize a real (small, permissively licensed) Ren'Py
   game and document the walkthrough.
5. **Translation memory**: fingerprint-based reuse of identical source
   strings across projects, before any model call.
