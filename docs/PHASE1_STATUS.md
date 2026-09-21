# Phase 1 Status — Stable (hardened)

## ✅ What works

```text
✅ Project structure with clean core / adapter / storage / cli boundaries
✅ Core localization model (normalized, serializable, deterministic ids)
✅ SQLite persistence with schema migrations (repository pattern)
✅ Deterministic translation cache (in-memory + SQLite, provider+model keyed)
✅ Pipeline abstraction: Detect → Extract → Normalize → Translate → Export
✅ Ren'Py detection + extraction (say / menu / translate-strings)
✅ Source references preserved (file + line + statement kind)
✅ TranslationProvider abstraction (provider-agnostic core)
✅ OpenAI-compatible API provider (works with OpenAI/OpenRouter/Gemini/Kimi/...)
   — BYO key via ALMURRIB_* env vars / .env; bounded backoff; no hardcoded keys
✅ Placeholder protection + post-translation validation
✅ Translation stage: skip-translated → TM reuse → cache → API → validate → persist
✅ Translation memory (exact fingerprint reuse across projects)
✅ Ren'Py reinjection: string-translation patch (game/tl/<lang>/strings.rpy),
   original game never modified
✅ CLI: detect / extract / translate / export / localize / inspect / db
   (force, provider/model/base-url flags, per-project scoping, exit codes)
✅ Provider registry (20+ definitions) + model discovery + Test Connection
✅ Cohere native adapter (chat + discovery, Command A family selectable)
✅ Provenance (provider/model/source), TM gating, OBSOLETE lifecycle
✅ Idempotent repeated runs, force semantics, deduplicated export
✅ GUI: provider/model discovery, force checkbox, output picker, log tools
✅ Offline test suite passes (live API + discovery tests opt-in via
   ALMURRIB_RUN_LIVE_TESTS=1)
✅ Real-game validated on Ren'Py's official demo "The Question" (77 entries)
```

## Real-game validation

Target: **"The Question"** — the demo game shipped with Ren'Py
(github.com/renpy/renpy, MIT). Only `game/script.rpy` is vendored as a
fixture (see `fixtures/the_question/ATTRIBUTION.md`).

Verified end-to-end (offline, deterministic fake provider):

```text
The Question (77 entries: 40 speaker dialogue, 31 narrator, 4 menu, 2 character names)
  → detect (renpy, confidence 0.90)
  → extract (77 normalized entries, speakers Sylvie/Me resolved, names extracted)
  → translate (77 translated, 0 failed — via RealTranslateStage)
  → export (game/tl/arabic/strings.rpy, 77 old/new pairs)
  → re-parse of the generated file returns all 77 pairs (loads cleanly)
  → original game/script.rpy byte-for-byte unchanged
```

The same flow with a **live API provider** requires only an API key:

```powershell
$env:ALMURRIB_API_KEY = "..."            # BYO key
$env:ALMURRIB_BASE_URL = "https://api.openai.com/v1"   # or OpenRouter/Gemini/Kimi/...
$env:ALMURRIB_MODEL = "gpt-4o-mini"
almurrib localize <game_dir> --out patch\
```

## ⚠️ Honest limitations

* The generated `strings.rpy` is syntactically valid, re-parseable by
  our own parser, **and VERIFIED loading inside the real Ren'Py 8.5.3
  engine on 2026-09-21**: the isolated `the_question_ar_test` copy renders
  Arabic dialogue, menu choices and character nameplates in-game (77 pairs,
  Vazirmatn font, native `ar` language button — user-verified).
* Live API translation is implemented and unit-tested with a mocked HTTP
  layer; the `tests/live/` path requires a user-supplied key and was not
  exercised here (no key available in this environment).
* Dialogue is localized via **string translation**, not per-statement
  `translate <lang> <id>:` blocks (those need engine-generated ids). String
  translation covers the same text and is the documented unsanctioned path.

## Phase 2 and beyond (not part of Phase 1)

Arabic reshaping/BiDi/fonts, advanced QA, glossary, character/style system,
other engines, runtime injection, TMX/XLIFF sharing, native Anthropic/Gemini
adapters, polished commercial UI.

