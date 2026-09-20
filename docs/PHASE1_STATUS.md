# Phase 1 Status — Complete (both halves)

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
✅ Tests: 66 passed + 1 live test (opt-in via ALMURRIB_RUN_LIVE_TESTS=1)
✅ Real-game validated on Ren'Py's official demo "The Question" (75 entries)
```

## Real-game validation

Target: **"The Question"** — the demo game shipped with Ren'Py
(github.com/renpy/renpy, MIT). Only `game/script.rpy` is vendored as a
fixture (see `fixtures/the_question/ATTRIBUTION.md`).

Verified end-to-end (offline, deterministic fake provider):

```text
The Question (75 entries: 40 speaker dialogue, 31 narrator, 4 menu)
  → detect (renpy, confidence 0.90)
  → extract (75 normalized entries, speakers Sylvie/Me resolved)
  → translate (75 translated, 0 failed — via RealTranslateStage)
  → export (game/tl/arabic/strings.rpy, 75 old/new pairs)
  → re-parse of the generated file returns all 75 pairs (loads cleanly)
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

* The generated `strings.rpy` is syntactically valid and re-parseable by
  our own parser, but **has not been loaded inside the Ren'Py engine
  itself** in this environment (no Ren'Py runtime installed). Loading it in
  a real game and confirming Arabic rendering is the remaining manual step.
* Live API translation is implemented and unit-tested with a mocked HTTP
  layer; the `tests/live/` path requires a user-supplied key and was not
  exercised here (no key available in this environment).
* Dialogue is localized via **string translation**, not per-statement
  `translate <lang> <id>:` blocks (those need engine-generated ids). String
  translation covers the same text and is the documented unsanctioned path.

## Phase 2 and beyond (not part of Phase 1)

Arabic reshaping/BiDi/fonts, advanced QA, glossary, character/style system,
other engines, runtime injection, TMX/XLIFF sharing, UI.

