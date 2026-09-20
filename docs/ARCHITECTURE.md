# Architecture Notes — Phase 1 (first 50%)

## Why the core is separated from the Ren'Py adapter

The core (`src/almurrib/core/`) knows *what a localization entry is*, *how
the pipeline flows*, and *how caching works* — but it has zero Ren'Py
knowledge. Engine knowledge lives behind the `EngineAdapter` protocol
(`core/engine.py`) and is registered in one place
(`engine_adapters/registry.py`). This is dependency inversion: the pipeline
depends on an abstraction, and each engine is a replaceable plugin. Ren'Py
is simply the first engine that proves the pattern; Unity/Unreal/RPG Maker
adapters later implement the same two methods (`detect`, `extract`).

## How the normalized localization model works

`LocalizationEntry` (`core/model.py`) is the stable internal contract every
stage speaks:

```text
id              deterministic content hash (engine + location + text)
engine          EngineType enum
source_text     the text to translate
translated_text target text (None until translated)
speaker         resolved display name when known
context         disambiguating context (e.g. "speaker:Eileen; file:...")
status          untranslated → translated → reviewed → approved (+ flagged/obsolete)
source_refs     precise origin: file + line + statement kind (for reinjection)
tags / qa_flags / metadata / version   future-proofing extension points
```

Entries serialize losslessly to/from dicts, so they flow through JSON
exports, the cache, and SQLite unchanged.

## How SQLite is used

All SQL lives in `src/almurrib/storage/`. `Database` opens the file and
applies ordered schema migrations (`schema_migrations` table; currently
version 1). `EntryRepository` is the only code that reads/writes the
`localization_entries` table; the rest of the app speaks domain objects.
Because entry ids are deterministic, `upsert` makes re-extraction
idempotent, and the conflict clause preserves an existing translation when
a fresh (untranslated) extraction of the same text arrives.

## How the cache is keyed

`make_cache_key()` hashes: engine + source_text + speaker + context +
target language + provider. The provider defaults to `"identity"` (nothing
translated yet); when llama.cpp/cloud providers land, their name+model join
the key so results never collide across providers. `TranslationCache`
(in-memory, reference implementation) and `SQLiteCache` (persistent) share
the same keying.

## How future engines plug in

1. Create `engine_adapters/<engine>/` implementing `EngineAdapter`.
2. Register it in `engine_adapters/registry.py::default_adapters()`.

Nothing in core, storage, or the CLI changes.

## Where the translation provider will connect

The pipeline already runs a `TranslateStage` between Normalize and
Validate (currently `NoOpTranslateStage`). The real provider (llama.cpp +
Qwen 2.5 locally; optional BYO-key cloud later) will implement that
interface, consult `SQLiteCache` before calling any model, and write
translations back onto entries — which then persist via the existing
repository upsert.

## Deliberate limits (first half of Phase 1)

No reinjection, no compiled `.rpyc` decompilation, no real translation, no
QA, no Arabic shaping/BiDi, no UI. The parser is intentionally
conservative: it extracts only unambiguous translatable text (say
statements, menu choices, `translate strings` pairs).
