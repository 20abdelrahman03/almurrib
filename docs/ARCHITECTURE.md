# Architecture Notes — Phase 1 (stable)

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
version 4: provenance columns, glossary table, composite entry identity).
`EntryRepository` is the only code that reads/writes the
`localization_entries` table; the rest of the app speaks domain objects.
Because entry ids are deterministic, `upsert` makes re-extraction
idempotent, and the conflict clause preserves an existing translation when
a fresh (untranslated) extraction of the same text arrives. Entry identity
is `(project_id, content-hash)`: identical text in two games never shares
a row. Bulk upserts run in one transaction; databases use WAL mode.

## How the cache is keyed

`make_cache_key()` hashes: engine + source_text + speaker + context +
target language + provider identity (`name:model`), so results never
collide across providers. `TranslationCache`
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

## Translation providers (Phase 1, second half)

The Core depends only on the `TranslationProvider` protocol
(`core/provider.py`): `config`, `capabilities()`, `translate()`,
`translate_batch()`. Concrete providers live under `providers/` and are
wired in by `providers/factory.py` — adding one never touches the pipeline.

* `providers/openai_compat.py` — one stdlib-`urllib` implementation for
  any OpenAI-compatible `POST {base_url}/chat/completions` API (OpenAI,
  OpenRouter, Gemini's compat endpoint, Kimi, a future local llama.cpp
  server). Selection is pure configuration (`base_url` + `model` + BYO
  `api_key`); nothing provider-specific lives in the Core.
* `providers/fake.py` — deterministic offline provider for tests/demos.

Configuration resolves from `ALMURRIB_*` environment variables → a local
`.env` → defaults (`core/config.py`). API keys are BYO, never committed,
never logged; they travel only in the `Authorization` header.

## Translation execution (cache + memory + placeholders)

`core/translate.py::RealTranslateStage` runs per entry: skip if already
translated → translation-memory reuse by exact fingerprint (source text +
speaker + context) → cache lookup (keyed by engine+text+speaker+context+
target lang + provider identity `name:model`) → provider batch →
placeholder validation → persist + cache save. A batch failure marks only
that batch failed and never corrupts previously-stored translations.

`core/placeholders.py` conservatively protects runtime tokens
(`{var}`, `{0}`, `%s/%d/%1$s`, `<color=red>`, `[variable]`, `\n`) and flags
any translation that loses them.

## Ren'Py reinjection

`engine_adapters/renpy/reinject.py` generates Ren'Py **string-translation**
files (`game/tl/<lang>/strings.rpy`, `old`/`new` pairs). We deliberately
use the string mechanism — not dialogue `translate <lang> <id>:` blocks —
because dialogue blocks require Ren'Py engine-assigned translation-unit
identifiers that cannot be computed from static parsing; string translation
matches by original text and is what Ren'Py documents for translations
produced outside the launcher. Output is a patch directory; the original
game is never modified.

## Translation provenance and memory rules

Every stored translation carries `translation_provider`, `translation_model`
and `translation_source` (`machine` | `human` | `imported`, schema v2). The
provider/model cache stays exact-keyed; translation memory reuses
human/imported work universally but machine output only for the same
`provider:model` that produced it — unless `ALMURRIB_REUSE_MACHINE_TM=1`
explicitly permits cross-model reuse. Legacy rows without provenance are
grandfathered as reusable so existing databases keep working.

## Lifecycle, force and repeated runs

Re-extraction is coherent: fresh entries without translations never reset
stored text/status/QA/provenance, and human `REVIEWED`/`APPROVED` states are
never demoted by re-imports. Entries missing from a fresh extraction become
`OBSOLETE` (history kept, excluded from translate/TM/export). `force`
ignores already-translated text, TM and cache reads, then overwrites
provenance. Re-runs are idempotent: stable row counts, byte-stable exports.

## Provider ecosystem

`providers/registry.py` defines every provider as data (id, protocol,
endpoints, discovery, verified flag). `openai_chat` definitions share the
generic transport; `cohere` has the one native adapter. `Fetch Models`
queries `GET {base}/models` (Cohere: `/v1/models?endpoint=chat`) and the GUI
discovers new registry entries with zero GUI changes. See
[PROVIDERS.md](PROVIDERS.md) for the verified matrix.

## Storage notes

Schema migrations are append-only (`schema_migrations`, currently v2).
Bulk upserts run in a single transaction; databases use WAL mode. Export
deduplicates identical source/translation pairs (differing translations for
one source are kept with a NOTE) and validates `target_lang` identifiers.

## Deliberate limits

No compiled `.rpyc` decompilation, no Arabic shaping/BiDi/fonts (Phase 2),
no advanced QA/glossary, no other engines yet. The parser extracts
only unambiguous translatable text (say statements, menu choices,
`translate strings` pairs). The Tkinter GUI is a developer tool with
provider/model discovery, testing, logging and run options — not a
commercial localization workbench.
