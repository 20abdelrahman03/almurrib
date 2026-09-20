# المعرب (Almurrib)

An **open-source Arabic game localization ecosystem** — not just a
translator. The long-term goal is a modular system that can take a real
game, understand how its text is stored, extract the translatable content,
translate it (locally first, cloud optional with BYO key), validate the
result, process Arabic correctly (reshaping, BiDi, fonts), and put the
translation back into the game.

> **Status: Phase 1 complete.** The repository contains the full Ren'Py
> localization pipeline: detection → extraction → normalized entries →
> API translation (BYO key) → cache + translation memory → placeholder
> validation → Ren'Py translation files. See
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and
> [docs/PHASE1_STATUS.md](docs/PHASE1_STATUS.md) for what is tested and
> the honest limitations.

## Why an ecosystem, not a tool

Inspired by GalTransl, LunaTranslator, VNTextPatch and Textractor: the
valuable thing is a modular ecosystem where extraction, translation, QA,
Arabic processing, reinjection, and runtime support work together — and
can survive beyond the original author. Mature open-source building
blocks (UnityPy, repak, llama.cpp, CTranslate2, Argos Translate, ...)
are integrated through adapters, never forked into the core.

## What works today

```text
Ren'Py game → detect → extract → normalize → translate (API, BYO key)
            → cache + translation memory → placeholder validation
            → generate game/tl/<lang>/strings.rpy patch (originals untouched)
```

Validated end-to-end on Ren'Py's official demo "The Question" (75 entries).

## Quick start

```powershell
# Python 3.11+ required. Runtime is stdlib-only; pytest is the only dev dep.
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"

# Desktop GUI (simple Tkinter frontend):
.\.venv\Scripts\almurrib-gui

# Offline walkthrough on the bundled tiny fixture (no API key needed):
.\.venv\Scripts\almurrib detect  fixtures\renpy_tiny
.\.venv\Scripts\almurrib extract fixtures\renpy_tiny --db demo.db --json out\entries.json
.\.venv\Scripts\almurrib inspect --db demo.db
.\.venv\Scripts\almurrib db      --db demo.db

# Full localization with a real API provider (Bring Your Own Key):
$env:ALMURRIB_API_KEY  = "..."                              # never committed
$env:ALMURRIB_BASE_URL = "https://api.openai.com/v1"        # or OpenRouter/Gemini/Kimi/...
$env:ALMURRIB_MODEL    = "gpt-4o-mini"
.\.venv\Scripts\almurrib localize <game_dir> --db demo.db --out patch\
# → patch\game\tl\arabic\strings.rpy, ready to drop into a copy of the game

# Run the tests (offline; live API test is opt-in):
.\.venv\Scripts\python -m pytest
```

Copy `.env.example` to `.env` for persistent local configuration.

### Build the Windows app

```powershell
.\.venv\Scripts\python build_exe.py     # → dist\Almurrib.exe
```

See [docs/GUI.md](docs/GUI.md) for the GUI and executable details.

## Layout

```text
src/almurrib/
  core/            normalized model, pipeline, cache, providers, placeholders,
                   config, translation stage, workflow (engine-agnostic)
  engine_adapters/ engine-specific code (renpy/: parser, adapter, reinjection)
  providers/       translation providers (openai_compat, fake) + factory
  storage/         SQLite database + repository + persistent cache
  cli/             command-line interface
tests/
  unit/            model, storage, cache, pipeline, parser, placeholders, ...
  integration/     CLI workflow, fixture round-trip, real-game validation
  live/            opt-in live API tests (ALMURRIB_RUN_LIVE_TESTS=1)
fixtures/
  renpy_tiny/      deterministic sample Ren'Py game
  the_question/    Ren'Py's official demo script (real-game validation)
docs/              architecture notes and phase status
```

## Principles

Open source first · local first · cloud optional (BYO key) · opt-in sharing
(open formats: TMX/XLIFF) · long-term maintainability · reuse existing open
source via adapters · our value is the integration layer.

## License

AGPL-3.0 — deliberately, to keep the ecosystem open. See
[LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
