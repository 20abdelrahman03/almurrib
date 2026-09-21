# Glossary — Phase 2b

Structured terminology (`src/almurrib/core/glossary.py`, stored in the same
SQLite database, migration v3, `glossary_entries` table).

## Model

```text
GlossaryEntry: source_term, target_term, type (character|term),
  gender (female|male|neutral|unknown), style (formal|standard|colloquial|
  rough|polite|childlike|technical|unspecified), pronunciation, notes,
  aliases, forbidden, enabled, project_id (0 = global/shared)
```

Scope: project entries win over global ones (case-insensitive); conflicts
(same source, different target) are rejected loudly at add/import, never
merged silently.

## Matching (deterministic)

Longest-first, case-insensitive, word-boundary aware (`Me` never matches
`memory`), non-overlapping spans, aliases included. A cheap substring
prefilter keeps 10k-entry lookups at ~3 ms. Same input + same glossary
version = same result (content hash in `Glossary.revision()`).

## Translation integration

```text
source → glossary matching → TranslationContext (speaker gender/style,
terms, nearby context) → provider prompt (generic, all transports) →
placeholder validation → Arabic QA → glossary QA → canonical Arabic
```

The model gets guidance; QA enforces it. No blind post-translation
substring replacement (it would break grammar and markup). TM/cache hits
are vetoed precisely when the stored text violates the ACTIVE glossary
(any glossary finding, error or warning): only affected entries fall
through to the provider, unrelated hits stay stable. Entry identity is
(project, content-hash), so identical text in two games never shares a row.

## QA semantics

* character-name mismatch → **error** (names don't inflect in Arabic)
* term mismatch → **warning**
* forbidden variant present → **error**
* comparison uses orthographic normalization (alef/ta/tashkeel/tatweel),
  so valid rendered forms are never flagged for byte-inequality.

## CLI

```powershell
almurrib glossary list [--game-dir ...]
almurrib glossary add --source Sylvie --target سيلفي --type character --gender female [--game-dir ...]
almurrib glossary import --file gloss.json [--game-dir ...]
almurrib glossary export --file gloss.json [--game-dir ...]
almurrib glossary clear [--game-dir ...]
```

Without `--game-dir`, entries are global. JSON and CSV formats are
documented by example in `export` output (format marker validated on
import; conflicts/malformed rows reported, never merged).

## GUI

The active project's glossary loads automatically on every Translate run
(global + project merged). Management (add/import) lives in the CLI in
this phase; the GUI shows glossary flag counts in the summary.
