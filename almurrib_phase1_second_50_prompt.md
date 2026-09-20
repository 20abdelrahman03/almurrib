# Prompt — Almurrib Phase 1: Second 50%
## Translation Providers → AI Translation → Ren'Py Reinjection → Real-Game E2E

You are continuing the **Almurrib (المعرب)** project.

The first 50% of Phase 1 has already been implemented and committed as the foundation.

Do NOT rebuild the foundation.
Do NOT replace the existing architecture unnecessarily.
Do NOT restart the project.

Your task is to implement the **remaining 50% of Phase 1** and turn the existing foundation into a real, usable Ren'Py localization pipeline.

---

# 1. Project Context

Almurrib is an open-source Arabic game localization ecosystem.

Its long-term purpose is:

> Give users a reusable system that can detect a game's engine, extract its text, normalize it, translate it, validate it, and put the translation back into the game.

The project is designed around:

- Open source
- Local-first philosophy
- Optional cloud APIs
- BYO API keys
- Opt-in sharing
- Engine adapters
- A common localization representation
- Translation memory and caching
- Arabic-specific processing later
- Long-term maintainability

The project is NOT intended to become dependent on one AI provider.

---

# 2. Important Change From the Original Phase 1 Plan

The original roadmap mentioned:

```text
llama.cpp + Qwen 2.5
```

as the local translation path.

For this implementation, **do not make local model inference a requirement**.

The user's current hardware is not intended to be the primary translation environment, so the architecture must prioritize:

> **API-based translation providers with BYO API keys.**

Local inference should remain an optional future provider.

The Core must remain provider-agnostic.

---

# 3. Existing Foundation

The previous 50% already implemented:

```text
src/almurrib/
├── core/
│   ├── model.py
│   ├── engine.py
│   ├── pipeline.py
│   ├── cache.py
│   └── errors.py
├── storage/
│   ├── database.py
│   ├── repository.py
│   └── cache.py
├── engine_adapters/
│   ├── registry.py
│   └── renpy/
│       ├── parser.py
│       ├── adapter.py
│       └── exporter.py
└── cli/
    └── main.py
```

It already has:

- LocalizationEntry
- SourceRef
- EngineAdapter protocol
- DetectionResult
- Pipeline abstraction
- Cache
- SQLite persistence
- Ren'Py detection
- Ren'Py extraction
- CLI
- Tests
- A tiny deterministic Ren'Py fixture

The previous run reported:

```text
31 tests passed
```

Treat this foundation as the starting point.

Before modifying anything:

1. Inspect the current repository.
2. Run the existing test suite.
3. Understand the current interfaces.
4. Preserve working behavior.
5. Only then implement the new work.

---

# 4. Goal of This Task

At the end of this task, the project should support:

```text
Ren'Py game
     ↓
Detection
     ↓
Extraction
     ↓
Normalized entries
     ↓
Translation Provider
     ↓
API translation
     ↓
Cache
     ↓
Stored translations
     ↓
Ren'Py translation files
     ↓
Playable localized game
```

The critical new milestone is:

> **A real Ren'Py project can be extracted, translated through an API provider, and have a usable Arabic translation output generated.**

---

# 5. What You Must Implement

## Part A — Formal Translation Provider Architecture

Create a clean provider abstraction.

The Core should not know whether translation is performed by:

- Gemini
- Kimi
- OpenAI-compatible APIs
- OpenRouter
- another API provider
- a future local model

The Core should only know about a generic interface.

Conceptually:

```python
class TranslationProvider(Protocol):
    name: str

    def capabilities(...):
        ...

    def translate(...):
        ...

    def translate_batch(...):
        ...
```

The exact design is up to you, but keep it clean.

The provider abstraction should support:

- source language
- target language
- text
- speaker/context where available
- glossary/context later
- deterministic provider identification
- errors
- batch translation where supported

Do not hardcode one provider into the Core.

---

# 6. API Provider Architecture

Implement at least **one real API provider**.

Prefer an API architecture that can be reused for multiple providers.

If the provider uses an OpenAI-compatible API shape, consider building:

```text
OpenAICompatibleProvider
```

instead of making separate duplicated implementations.

The configuration should allow:

```text
provider
base_url
model
api_key
timeout
```

Do not hardcode API keys into source code.

Use environment variables and/or a local configuration mechanism.

Example concept:

```text
ALMURRIB_API_KEY
ALMURRIB_BASE_URL
ALMURRIB_MODEL
```

Exact names are up to you.

---

# 7. Do Not Assume a Free API Is Permanently Free

The project must not hardcode assumptions like:

> "Provider X is always free."

Free tiers change.

Instead, design the provider system so the user supplies:

- API key
- endpoint
- model

and the provider simply calls the configured API.

If you need to choose a default provider for testing, use a provider that is currently accessible to the user/environment, but keep the implementation replaceable.

Do not build the architecture around a temporary pricing policy.

---

# 8. Translation Prompt Design

Create a dedicated translation prompt/template.

The translator should receive enough context to preserve meaning.

At minimum consider:

```text
source text
speaker
context
source language
target language
```

The translator must be instructed to:

- translate only the requested text
- not add explanations
- preserve placeholders
- preserve variables
- preserve escape sequences
- preserve formatting tokens
- avoid translating identifiers
- respect speaker/context when supplied

For example:

```text
Hello, {player_name}!
```

must not become:

```text
مرحبًا!
```

It must preserve:

```text
{player_name}
```

This is critical for game localization.

---

# 9. Placeholder Protection

Implement a basic placeholder protection/validation system.

Detect common tokens such as:

```text
{player_name}
{0}
%s
%d
%1
<color=red>
</color>
\\n
[variable]
```

The exact patterns should be conservative.

Before sending text to the provider, identify protected tokens.

After translation:

1. verify all required tokens still exist
2. verify they were not accidentally translated
3. flag the translation if tokens are missing or changed

Do not attempt to support every possible game's syntax yet.

Build a clean extensible mechanism.

---

# 10. Translation Cache Integration

The previous foundation already has a cache.

Now actually connect translation execution to it.

Required behavior:

```text
translation request
       ↓
calculate cache key
       ↓
cache hit?
   ┌───┴───┐
  YES      NO
   ↓        ↓
return     API
           ↓
         result
           ↓
        validate
           ↓
        cache save
```

The same text should not trigger unnecessary API requests.

The cache key must account for relevant differences such as:

- source text
- speaker/context where relevant
- source language
- target language
- provider
- model

Do not accidentally reuse a translation from a different model/provider when the configuration matters.

---

# 11. Batch Translation

Implement batching where practical.

Do not blindly send 10,000 independent HTTP requests.

The provider abstraction should support something like:

```text
translate_batch(entries)
```

The batch implementation must still preserve entry identity.

If a batch fails:

- provide clear errors
- avoid corrupting stored translations
- allow retry
- do not lose successfully cached previous translations

Do not build an extremely sophisticated queue yet.

---

# 12. Translation Execution

Connect the provider to the existing Pipeline.

The pipeline should now be capable of:

```text
Detect
→ Extract
→ Normalize
→ Translate
→ Validate
```

The translation stage should:

1. receive normalized entries
2. skip entries already translated when appropriate
3. check cache
4. send only required entries to the provider
5. validate responses
6. store translations
7. preserve source information

The Core should remain provider-agnostic.

---

# 13. Ren'Py Reinjection

This is one of the most important parts of this task.

Implement the Ren'Py write-back/export path.

The goal is to generate usable Ren'Py translation files.

Prefer the standard Ren'Py translation mechanism when possible rather than destructively rewriting the original source scripts.

The generated output should conceptually resemble:

```text
game/
└── tl/
    └── arabic/
        ├── strings.rpy
        └── ...
```

The exact structure depends on what the source scripts contain.

Use the previously preserved SourceRef information.

---

# 14. Preserve Source Safety

Never overwrite the original game by default.

The default workflow should be:

```text
Original game
     ↓
Read-only extraction
     ↓
Translation
     ↓
Generated localization output
```

The user should receive a separate output directory or localization patch.

If something goes wrong:

```text
Original game remains untouched.
```

This is a critical design requirement.

---

# 15. Ren'Py Translation Types

The implementation should support the extraction patterns already represented by the current fixture.

At minimum, handle the currently supported:

- dialogue/say entries
- menu entries
- existing translate-string style entries

Do not claim universal Ren'Py support.

If unsupported syntax is encountered:

- skip safely
- report it
- do not silently corrupt the file

---

# 16. Round-Trip Tests

Create tests proving:

```text
source fixture
→ extract
→ translate using fake/stub provider
→ export translation
→ inspect output
```

Use a deterministic fake provider in tests.

Do NOT make the test suite depend on a live external API.

Tests must remain offline and reproducible.

---

# 17. API Integration Tests

Separate live API tests from normal tests.

For example:

```text
tests/
├── unit/
├── integration/
└── live/
```

The default test suite must not require an API key.

A live API test may be enabled explicitly through an environment variable.

For example:

```text
ALMURRIB_RUN_LIVE_TESTS=1
```

Do not leak API keys in logs.

---

# 18. Real Ren'Py Game Validation

After the fixture works, validate against a small real Ren'Py game.

Prefer a game whose license explicitly permits the required testing/distribution of the source or whose source is otherwise suitable for this engineering validation.

Do not download or redistribute copyrighted game content unnecessarily.

The validation should prove:

```text
real game
→ detect
→ extract
→ translate
→ generate localization files
→ game can load the localization
```

Do not claim full compatibility from one test game.

Document exactly what was tested.

---

# 19. Translation Memory

Implement the first useful form of translation memory.

The existing fingerprint mechanism can be used as the basis.

The system should be able to recognize:

```text
Project A:
"Hello, world!"
→ "مرحبًا بالعالم"

Project B:
"Hello, world!"
→ reuse previous translation
```

But be careful:

Context can matter.

Do not blindly reuse a translation when speaker/context differs in a way that could change meaning.

The system should retain enough metadata to make this behavior controllable.

---

# 20. CLI Expansion

Extend the CLI to make the new workflow usable.

Conceptually support commands like:

```text
detect
extract
translate
export
localize
inspect
db
```

A high-level command such as:

```text
almurrib localize <game>
```

may orchestrate:

```text
detect
→ extract
→ translate
→ export
```

but keep individual commands available for debugging.

The CLI should report useful progress.

Example:

```text
Engine: Ren'Py
Entries extracted: 1,248
Cache hits: 934
API translations: 314
Failed: 3
Output: ...
```

---

# 21. Configuration

Add a clean configuration layer.

Configuration should be able to define:

```text
provider
model
base_url
API key
source language
target language
batch size
timeouts
database path
output directory
```

Secrets must never be committed.

Provide an example configuration file such as:

```text
.env.example
```

with placeholders only.

---

# 22. Error Handling

The project already has stage-tagged errors.

Extend them where necessary.

Errors should distinguish between:

```text
Extraction error
Translation API error
Authentication error
Rate limit
Timeout
Invalid provider response
Placeholder validation error
Export error
```

The CLI should present human-readable errors.

Do not expose raw stack traces unless debug mode is enabled.

---

# 23. Retry and Rate Limits

Implement a modest retry strategy for transient API failures.

Examples:

- timeout
- temporary network error
- HTTP 429
- temporary server errors

Do NOT build a huge distributed queue.

A simple bounded exponential backoff is enough.

Respect provider rate limits.

Do not aggressively hammer free APIs.

---

# 24. Provider-Agnostic Design

The architecture should make this possible:

```text
TranslationProvider
       │
       ├── Provider A
       ├── Provider B
       ├── Provider C
       └── Future Local Model
```

Adding a provider should not require changing the Core pipeline.

This is one of the most important architectural goals of this task.

---

# 25. What NOT to Implement Yet

Even after this task, do NOT implement:

- advanced Arabic reshaping
- advanced BiDi engine
- automatic Arabic font injection
- sophisticated Arabic word wrapping
- character gender system
- dialect/style system
- advanced QA engine
- Unity adapter
- Unreal adapter
- RPG Maker adapter
- BepInEx runtime translation
- UE4SS runtime translation
- OCR
- adaptive runtime translation
- TMX/XLIFF community sharing
- LoRA training
- full Tauri UI redesign
- community infrastructure

Those belong to later phases.

---

# 26. Arabic Handling in This Phase

Do not pretend Phase 1 has the complete Arabic rendering system.

The target language is Arabic, so translation output should be Arabic.

But the advanced Arabic rendering layer is intentionally deferred to Phase 2.

For now:

- correctly store UTF-8 Arabic
- correctly export Arabic text
- do not corrupt Unicode
- preserve text exactly through storage
- do not claim that advanced RTL rendering is solved

---

# 27. Security and Privacy

The system must:

- never hardcode secrets
- never print API keys
- never upload source text except when the selected provider requires it
- clearly identify when an external API is being used
- keep local data local by default
- allow users to choose providers

If an API is used, make the network boundary clear in logs/output.

---

# 28. Documentation

Update:

```text
README.md
docs/ARCHITECTURE.md
docs/PHASE1_STATUS.md
THIRD_PARTY_NOTICES.md
```

Document:

- provider architecture
- configuration
- API setup
- translation workflow
- Ren'Py export
- limitations
- tested game/fixture
- remaining Phase 1 work, if any

Do not claim features that were not actually tested.

---

# 29. Definition of Done

Do not declare this task complete merely because code exists.

The second 50% is complete when the following is demonstrably true:

```text
✅ Existing 31+ tests still pass
✅ TranslationProvider abstraction exists
✅ At least one real API provider works
✅ API key is configurable and not hardcoded
✅ Cache prevents duplicate translations
✅ Placeholder preservation is validated
✅ Translation stage performs real translation
✅ Translations persist in SQLite
✅ Ren'Py localization files are generated
✅ Original game files are not overwritten by default
✅ Offline tests use a fake provider
✅ Live API tests are separated
✅ CLI can run the translation/export workflow
✅ A suitable real Ren'Py project has been tested
✅ Documentation reflects actual behavior
```

The ultimate Phase 1 success condition is:

```text
Real Ren'Py Game
       ↓
Almurrib
       ↓
Extract
       ↓
Translate through API
       ↓
Validate
       ↓
Generate Ren'Py localization
       ↓
Launch game
       ↓
Arabic text appears
```

That is the point at which Phase 1 can honestly be considered complete.

---

# 30. Execution Protocol

Before making changes:

1. Inspect the repository.
2. Run all existing tests.
3. Read the existing architecture.
4. Identify the current pipeline extension points.
5. Identify what the existing Ren'Py exporter already supports.
6. Propose the implementation plan.

Then implement in small milestones:

```text
Milestone 1 — TranslationProvider abstraction
Milestone 2 — API provider
Milestone 3 — Cache integration
Milestone 4 — Translation stage
Milestone 5 — Placeholder validation
Milestone 6 — Ren'Py reinjection
Milestone 7 — CLI workflow
Milestone 8 — Translation memory
Milestone 9 — Real-game validation
Milestone 10 — Documentation + final tests
```

After every milestone:

- run tests
- inspect failures
- fix regressions
- keep the repository runnable

Do not rewrite working components unnecessarily.

---

# 31. Final Report Requirements

When finished, provide a concise but concrete report containing:

## Implementation
What was actually built.

## Files Changed
Important files and why they changed.

## Tests
Exact test count and results.

## API Provider
Which provider/endpoint was tested and how it is configured.

## Cache
How cache hits/misses work.

## Ren'Py Export
Exactly what forms of Ren'Py localization are supported.

## Real Game Test
Name/type of the test project and exactly what was verified.

## Limitations
Anything still unsupported.

## Phase 1 Status
State whether Phase 1 is now actually complete according to the definition of done above.

Do not say "complete" if the real-game end-to-end condition has not been demonstrated.

---

# Final Instruction

Build the remaining 50% of Phase 1 **on top of the existing Almurrib foundation**.

Do not rebuild it.

Do not turn this into a generic translation script.

Do not hardcode one AI provider into the Core.

Do not make local model inference mandatory.

The result should be the first genuinely usable version of Almurrib:

> **A modular, open-source game localization pipeline that can extract text from a real Ren'Py game, translate it through a configurable API provider, preserve game-specific tokens, cache the results, generate Ren'Py localization files, and produce a testable Arabic-localized game without modifying the original game by default.**
