# المعرب (Almurrib)

An **open-source Arabic game localization ecosystem** — not just a
translator. The long-term goal is a modular system that can take a real
game, understand how its text is stored, extract the translatable content,
translate it (locally first, cloud optional with BYO key), validate the
result, process Arabic correctly (reshaping, BiDi, fonts), and put the
translation back into the game.

> **Status: Phase 1, first 50% (foundation).** Today the repository
> contains the core domain model, SQLite persistence, a deterministic
> translation cache, the pipeline abstraction, the Ren'Py adapter
> (extraction-first), a CLI, and a deterministic test fixture. See
> [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and
> [docs/PHASE1_STATUS.md](docs/PHASE1_STATUS.md) for what is and is not
> implemented.

## Why an ecosystem, not a tool

Inspired by GalTransl, LunaTranslator, VNTextPatch and Textractor: the
valuable thing is a modular ecosystem where extraction, translation, QA,
Arabic processing, reinjection, and runtime support work together — and
can survive beyond the original author. Mature open-source building
blocks (UnityPy, repak, llama.cpp, CTranslate2, Argos Translate, ...)
are integrated through adapters, never forked into the core.

## What works today

```text
Ren'Py fixture → Ren'Py adapter → extraction → normalized entries → SQLite → CLI inspection
```

## Quick start

```powershell
# Python 3.11+ required. Runtime is stdlib-only; pytest is the only dev dep.
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"

# Try it on the bundled tiny Ren'Py fixture:
.\.venv\Scripts\almurrib detect  fixtures\renpy_tiny
.\.venv\Scripts\almurrib extract fixtures\renpy_tiny --db demo.db --json out\entries.json
.\.venv\Scripts\almurrib inspect --db demo.db
.\.venv\Scripts\almurrib db      --db demo.db

# Run the tests:
.\.venv\Scripts\python -m pytest
```

## Layout

```text
src/almurrib/
  core/            normalized model, pipeline, cache, errors (engine-agnostic)
  engine_adapters/ engine-specific code (renpy/ today; unity/unreal/... later)
  storage/         SQLite database + repository + persistent cache
  cli/             command-line interface
tests/             model, storage, cache, pipeline, parser, adapter, CLI tests
fixtures/renpy_tiny/   deterministic sample Ren'Py game
docs/              architecture notes and phase status
```

## Principles

Open source first · local first · cloud optional (BYO key) · opt-in sharing
(open formats: TMX/XLIFF) · long-term maintainability · reuse existing open
source via adapters · our value is the integration layer.

## License

AGPL-3.0 — deliberately, to keep the ecosystem open. See
[LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
