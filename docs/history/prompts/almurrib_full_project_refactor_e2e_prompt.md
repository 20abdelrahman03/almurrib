# Almurrib — Full Project Refactor, Hardening, and End-to-End Validation

You are the lead software architect, senior Python engineer, localization engineer, QA engineer, performance engineer, and release engineer for **Almurrib (المعرب)**.

This is NOT a feature sprint.

This is a **full-project engineering refactor and hardening pass** over the entire current repository.

Your mission is to understand every part of the project, find real problems, improve architecture and algorithms, remove duplication and technical debt, fix bugs, strengthen E2E behavior, improve maintainability and packaging, and leave the repository in a genuinely hardened state for the current scope.

Do not optimize for a nice-looking report.

Optimize for:

- correctness
- deterministic behavior
- maintainability
- clean architecture
- reliability
- data integrity
- testability
- performance
- packaging reliability
- clear documentation
- future extensibility

---

# 0. CURRENT PROJECT CONTEXT

Almurrib is an open-source Arabic game localization ecosystem.

The intended architecture is broadly:

```text
GUI / CLI
    ↓
Workflow / Pipeline
    ↓
Core domain
    ├── LocalizationEntry
    ├── TranslationContext
    ├── Glossary
    ├── QA
    ├── Cache / TM
    ├── Provenance
    └── Overlay
    ↓
Arabic layer
    ├── normalization
    ├── masking
    ├── reshaping
    ├── BiDi
    ├── wrapping
    ├── font resources
    └── font metrics
    ↓
Provider abstraction
    ↓
Engine adapters
    ↓
Export / localization output
```

Current milestones include:

- Phase 1 foundation
- Ren'Py extraction/translation/export
- provider ecosystem
- GUI + CLI
- Arabic processing
- Arabic QA
- glossary
- gender/style translation context
- real font metrics
- RTL-capable Almurrib UI
- localization overlay architecture
- browser manual acceptance fixture
- Ren'Py visual-test fixture

The current reports reached approximately:

```text
357 tests passing
```

The browser fixture also demonstrated Arabic output.

A real manual observation exposed this case:

```text
Sylvie / Mira / Captain Rowan → translated
Alex → remained "Alex"
```

This MUST be investigated rather than patched blindly.

---

# 1. THIS IS A REAL REFACTOR

Do NOT treat this as:

> "Run tests, fix failures, stop."

Treat it as:

> "Assume hidden architectural, algorithmic, integration, packaging, and maintainability bugs exist. Find them proactively."

Inspect:

- every source file
- every test file
- configuration
- packaging
- documentation
- fixtures
- resources
- schemas/migrations
- scripts
- CLI
- GUI
- providers
- engine adapters
- Arabic layer
- browser acceptance fixture

Do not review only files you expect to change.

---

# 2. GIT SAFETY

Before changes:

```powershell
git status
git diff
git branch --show-current
```

Preserve existing user work.

Do NOT:

- reset
- clean destructive user files
- discard unrelated changes
- rewrite history
- commit automatically

At the end:

```powershell
git status
git diff --stat
git diff --check
```

Do not commit unless explicitly requested.

---

# 3. FULL REPOSITORY INVENTORY

Inspect the actual repository tree, including relevant directories such as:

```text
src/
tests/
fixtures/
docs/
tools/
gui/
providers/
storage/
engine_adapters/
arabic/
scripts/
```

and root files such as:

```text
pyproject.toml
README.md
THIRD_PARTY_NOTICES.md
.env.example
build_exe.py
*.spec
```

Do not assume the structure is exactly this.

Identify:

- source modules
- entry points
- dependency graph
- dead code
- duplicate code
- duplicate concepts
- temporary code
- test-only code
- production code
- generated artifacts
- stale documentation
- compatibility shims
- abandoned implementations

---

# 4. RECONSTRUCT THE REAL ARCHITECTURE

Before refactoring, determine the actual architecture from code.

Map boundaries such as:

```text
GUI
 ↓
Workflow
 ↓
Pipeline
 ↓
Core domain
 ↓
Storage
 ↓
Translation provider
 ↓
QA
 ↓
Export
 ↓
Engine adapter
```

For each boundary determine:

- ownership
- inputs
- outputs
- side effects
- persistence
- error behavior
- test coverage
- dependency direction

Find cycles and responsibility violations.

---

# 5. ARCHITECTURAL RULES

Converge toward clear boundaries:

## Core
Domain/business logic.

## Storage
Database/persistence only.

## Providers
External/local model access only.

## Arabic layer
Arabic processing only.

## Engine adapters
Engine-specific extraction/export/runtime details only.

## GUI
Presentation/orchestration only.

## CLI
Command-line orchestration only.

## Tools
Build/test/development helpers, never hidden production business logic.

No layer should secretly own another layer's responsibilities.

---

# 6. FIND AND REMOVE DUPLICATION

Search for duplicate implementations of:

- normalization
- placeholder parsing
- QA
- glossary matching
- path resolution
- provider error handling
- configuration parsing
- model representations
- localization entry definitions
- serialization
- CLI/GUI workflow logic
- Ren'Py parsing/export
- Arabic processing
- font handling

Consolidate genuinely duplicated behavior into one authoritative implementation.

Do not create abstractions merely for abstraction's sake.

---

# 7. CORE DOMAIN REVIEW

Audit all core models, including concepts equivalent to:

```text
LocalizationEntry
EntryStatus
SourceRef
EngineType
TranslationContext
GlossaryEntry
OverlayPlan
QAResult
QAFlag
ProviderInfo
ModelInfo
FontAsset
FontMetrics
TextMetrics
```

Check:

- invariants
- equality/hash behavior
- mutability
- serialization
- stable IDs
- versioning
- nullability
- enums
- invalid states
- accidental coercion

Make illegal states difficult to represent.

---

# 8. DATABASE / STORAGE REVIEW

Audit the complete SQLite layer.

Check:

- schema
- migrations
- indexes
- uniqueness
- foreign keys
- project scoping
- game scoping
- provider/model provenance
- glossary scope
- cache scope
- transaction boundaries
- WAL behavior
- connection lifecycle
- schema versioning
- duplicate rows
- stale rows
- obsolete rows
- migration safety

Investigate and fix real risks such as:

- project-relative path collisions
- TM/cache contamination
- provider provenance leakage
- stale OBSOLETE records
- repeated-run inconsistencies
- status inconsistencies

Do not merely document them.

---

# 9. CACHE / TRANSLATION MEMORY REVIEW

Audit all dimensions that can affect reuse:

```text
cache
TM
provenance
glossary revision
provider
model
project
source hash
context
```

Verify:

- stale translations cannot leak across projects
- glossary changes invalidate relevant translations
- provider/model changes do not incorrectly reuse incompatible results
- failed/flagged results do not become authoritative
- manual corrections are not silently overwritten
- force behavior is actually force
- repeated runs avoid unnecessary provider calls
- errors are not cached as successful translations
- provenance is complete enough for auditing

Make behavior deterministic.

---

# 10. TRANSLATION PIPELINE REVIEW

Audit:

```text
detect
→ extract
→ normalize
→ glossary context
→ translate
→ placeholder validation
→ Arabic QA
→ persistence
→ export
```

Check:

- stage boundaries
- retry semantics
- partial failures
- batch behavior
- single-item fallback
- error propagation
- status transitions
- idempotency
- cancellation
- progress reporting
- logging
- deterministic re-runs

No silent failure swallowing.

---

# 11. PROVIDER ECOSYSTEM REVIEW

Audit every provider implementation.

Check:

- normalized interface
- model discovery
- capabilities
- error normalization
- authentication failures
- rate limits
- malformed responses
- empty responses
- timeouts
- retries
- batch failure
- single-item fallback
- model IDs
- provenance
- context injection
- secret handling

Keep providers provider-agnostic from core business logic.

Do not leak provider-specific logic into the pipeline.

---

# 12. GLOSSARY REVIEW — INVESTIGATE THE ALEX CASE

Find the real reason:

```text
Alex
```

remained untranslated while other names worked.

Investigate:

- absent glossary entry
- alias matching
- word-boundary logic
- speaker metadata
- glossary scope
- provider ignoring context
- deterministic fixture behavior
- stale cache
- export omission
- proper-noun heuristics

Do NOT simply add `Alex -> أليكس` and stop.

First determine:

> Why did Alex remain untranslated?

If expected, document why.

If buggy, reproduce, fix root cause, and add a regression test.

---

# 13. GLOSSARY ALGORITHM REVIEW

Deeply test:

- longest-first matching
- overlapping terms
- boundaries
- punctuation
- apostrophes
- case sensitivity
- aliases
- forbidden terms
- character names
- inflections
- substring collisions such as `Me` vs `memory`
- Unicode variants
- mixed Arabic/Latin
- multiple matches
- conflict resolution

Measure complexity.

Where justified, evaluate algorithms such as:

- precompiled patterns
- tries
- Aho–Corasick
- indexed token matching

Do not optimize blindly.

Benchmark before and after.

Preserve deterministic ordering.

---

# 14. ARABIC LAYER REVIEW

Audit every module under:

```text
arabic/
```

Review:

- normalization
- masking
- reshaping
- BiDi
- wrapping
- fonts
- metrics
- QA

Attack with:

- NFC/NFD
- combining marks
- Tatweel
- ZWJ/ZWNJ
- directional marks
- punctuation
- Arabic/Latin digits
- mixed scripts
- emoji
- URLs
- placeholders
- markup
- newlines
- huge strings

Canonical Arabic must remain recoverable.

Render-ready text must never replace canonical text.

---

# 15. BIDI EDGE-CASE REVIEW

The earlier work found:

```text
python-bidi AssertionError on LRI/PDI
```

Verify the workaround is:

- correct
- scoped
- deterministic
- reversible
- collision-safe
- documented

Attack it with:

```text
LRI
RLI
FSI
PDI
LRE
RLE
PDF
LRM
RLM
ALM
```

Do not assume PUA masking is automatically safe.

---

# 16. WRAP / FONT METRICS REVIEW

Audit:

```text
FontMetrics
TextMetrics
wrap
```

Check:

- glyph measurement
- missing glyphs
- fallback fonts
- invalid/corrupt fonts
- large font sizes
- zero/negative width
- long URLs
- unbreakable tokens
- placeholders
- markup
- Arabic + Latin
- Arabic + numbers

Cache expensive operations responsibly.

Measure performance.

---

# 17. QA ENGINE REVIEW

Audit every QA rule for:

- false positives
- false negatives
- severity
- evidence
- stable rule IDs
- explainability
- composition
- registration
- glossary integration
- placeholder checks
- mixed-direction checks
- punctuation
- source-copy
- Latin heuristic
- length heuristic

QA must inspect, not silently mutate, translations.

---

# 18. OVERLAY ARCHITECTURE REVIEW

The product rule is:

```text
Game base/original locale = English whenever possible
Displayed game localization = Arabic
Almurrib UI locale = independent
```

Verify:

- overlay is represented cleanly
- future engine adapters can consume base locale, displayed locale, strategy
- no Phase 3 runtime injection is implemented now

---

# 19. GUI REVIEW

Audit:

- state management
- widget lifetime
- event handling
- rebuilding
- RTL toggle
- LTR toggle
- clipboard
- logging
- provider fields
- model discovery
- output path
- progress
- errors
- settings
- environment loading
- secrets
- resizing
- Windows behavior

Test:

- Arabic ↔ English repeatedly
- provider/model changes
- duplicate runs
- failed provider
- missing key
- invalid directory
- long error
- empty fields
- clipboard operations

No stale UI state.

---

# 20. CLI REVIEW

Audit all commands, including:

```text
--help
detect
extract
inspect
db
translate
export
localize
glossary
```

Check:

- help
- exit codes
- Unicode paths
- spaces
- errors
- force behavior
- logging
- progress
- deterministic output

CLI and GUI must share application services rather than duplicating business logic.

---

# 21. REN'PY ADAPTER REVIEW

Audit:

- detection
- extraction
- normalization
- source references
- dialogue
- choices
- speaker names
- translation blocks
- export
- reparse
- encoding
- escapes
- quoting
- duplicate translations

Test:

```text
tiny fixture
real fixture
generated fixture
```

Explicitly distinguish:

- dialogue text
- speaker names
- UI strings
- hard-coded language menus

Do not assume all visible text uses the same translation mechanism.

---

# 22. BROWSER ACCEPTANCE FIXTURE REVIEW

Audit:

```text
almurrib_phase2_manual_test/
```

Verify:

- English mode
- Arabic mode
- overlay mode
- debug panel
- source/output consistency
- branch behavior
- placeholder handling
- glossary display
- deterministic outputs

Keep test harness code clearly separate from production code.

---

# 23. TEST SUITE REVIEW

Do not trust the count.

Classify tests:

```text
unit
integration
workflow
E2E
adversarial
fuzz-like
performance
packaging
manual acceptance
regression
```

Find gaps.

Add tests for:

- every discovered bug
- every important boundary
- serialization
- migrations
- provider errors
- status transitions
- cache invalidation
- glossary revisions
- project isolation
- GUI critical flows
- EXE resource resolution

---

# 24. PROPERTY / FUZZ TESTING

Expand fuzz-like tests for:

- Unicode
- placeholders
- glossary matching
- punctuation
- mixed scripts
- URLs
- long strings
- direction marks
- whitespace
- supported markup

Preserve invariants such as:

```text
placeholder_set(before) == placeholder_set(after)
```

where applicable.

```text
canonical_text remains unchanged by render processing
```

```text
same input + same configuration = deterministic output
```

```text
re-running workflow is stable
```

---

# 25. PERFORMANCE REVIEW

Benchmark meaningful workloads:

```text
100 entries
1,000 entries
10,000 entries
50,000 where practical
```

Measure:

- extraction
- glossary matching
- translation preparation
- QA
- wrapping
- font measurement
- persistence
- export
- repeated run
- cache-hit run

Fix algorithmic bottlenecks when justified.

Record before/after numbers for real optimizations.

---

# 26. ERROR HANDLING REVIEW

Search aggressively for:

```text
except Exception
pass
silent fallback
return None
TODO
FIXME
HACK
```

Every broad exception must have a justification.

Classify:

```text
user input
configuration
provider/network
data corruption
engine parsing
internal programming error
```

Ensure errors retain root cause and useful context.

Never leak secrets.

---

# 27. SECURITY REVIEW

Audit:

- API keys
- `.env`
- logs
- traces
- temp files
- subprocesses
- arbitrary file writes
- untrusted game content
- unsafe archive extraction if relevant
- browser fixture behavior

Fix reasonable application security defects.

Do not turn this into an unrelated security product.

---

# 28. CONFIGURATION REVIEW

Determine one clear precedence order for:

```text
defaults
.env
config file
CLI
GUI
provider/model overrides
```

Remove contradictory behavior.

Document the final precedence.

---

# 29. WINDOWS / PATH REVIEW

Test:

- Arabic directories
- spaces
- non-ASCII paths
- relative paths
- absolute paths
- different working directories
- PyInstaller resource paths
- temp directories
- output directories

Never assume cwd == repository root.

---

# 30. PACKAGING / EXE REVIEW

Build:

```powershell
.\.venv\Scripts\python build_exe.py
```

Then launch from a different working directory.

Verify:

- imports
- Arabic dependencies
- glossary
- fonts
- i18n
- database
- configs
- resources
- error handling

No source-tree-relative assumptions.

---

# 31. DEPENDENCY AUDIT

For every runtime dependency:

- version
- purpose
- license
- transitive dependencies
- packaging impact
- actual necessity

Remove unused dependencies.

Ensure:

```text
pyproject.toml
THIRD_PARTY_NOTICES.md
```

match reality.

---

# 32. CODE QUALITY

Improve where justified:

- naming
- typing
- function size
- cyclomatic complexity
- side effects
- mutable defaults
- globals
- dead code
- unreachable branches
- duplicated constants
- magic values
- overly clever logic

Prefer readable explicit code.

Do not create needless abstractions.

---

# 33. API STABILITY

Identify interfaces used by:

- CLI
- GUI
- tests
- providers
- adapters
- tools

Do not break public/internal APIs unnecessarily.

If an API must change:

- update all call sites
- add regression tests
- update docs
- preserve compatibility where practical

---

# 34. DOCUMENTATION CONSISTENCY

Cross-check:

```text
README
docs
CLI help
GUI labels
code behavior
```

Fix contradictions.

Clearly distinguish:

```text
implemented
tested
integration verified
E2E verified
manually verified
unverified
future
```

Never claim unsupported behavior.

---

# 35. PHASE 3 FIREWALL

Do NOT implement:

- Unity
- Unreal
- RPG Maker
- BepInEx runtime injection
- UE4SS
- production VNTextPatch integration
- runtime hook frameworks
- Velopack production release work
- SignPath setup
- community TMX/XLIFF sharing
- LoRA/model training

You may improve interfaces needed by future adapters.

Do not implement Phase 3 itself.

---

# 36. FULL E2E MATRIX

Execute all meaningful scenarios:

## A. Clean run

```text
detect
→ extract
→ translate
→ QA
→ persist
→ export
→ reparse
```

## B. Second run

Expected:

```text
stable / cache hits / no unnecessary provider calls
```

## C. Force

Expected real reprocessing where policy says so.

## D. Glossary change

Relevant entries invalidate; unrelated entries remain stable.

## E. Provider change

No incorrect stale reuse.

## F. Project isolation

Project A cannot contaminate Project B.

## G. Partial provider failure

Successful entries remain valid; failed entries recover cleanly.

## H. Export/reparse

Generated output reparses cleanly.

## I. Arabic processing

Canonical remains logical; render-ready is derived.

## J. GUI

Same business behavior as CLI.

## K. EXE

Works outside repository cwd.

## L. Browser manual fixture

English, Arabic, overlay, glossary, QA.

---

# 37. REGRESSION DISCIPLINE

For every genuine bug:

```text
1. Reproduce
2. Add regression test
3. Fix root cause
4. Targeted tests
5. Full suite
6. Verify no unrelated regression
```

Never patch only the visible symptom.

---

# 38. FINAL SELF-AUDIT

After all tests pass:

STOP.

Review the project as if inheriting it from another engineer.

Look for:

- accidental coupling
- hidden state
- stale APIs
- duplicate logic
- bad complexity
- inconsistent errors
- missing tests
- documentation drift
- packaging bugs
- cache contamination
- provider leaks
- Unicode mistakes
- RTL mistakes
- glossary ambiguity
- GUI state bugs
- Windows path bugs

Fix anything genuinely found.

---

# 39. DEFINITION OF DONE

Do not stop merely because tests are green.

The task is complete when:

## Architecture
- [ ] responsibilities are clear
- [ ] duplicated concepts are consolidated
- [ ] dependency direction is sane
- [ ] no unnecessary parallel architecture

## Algorithms
- [ ] glossary matching correct/deterministic
- [ ] cache/TM behavior correct
- [ ] Arabic masking correct
- [ ] wrapping correct
- [ ] QA logic correct
- [ ] performance reasonable

## Data
- [ ] persistence safe
- [ ] migrations safe
- [ ] project isolation correct
- [ ] provenance correct

## Translation
- [ ] provider abstraction clean
- [ ] context correct
- [ ] invalidation correct
- [ ] retries/errors correct

## Arabic
- [ ] canonical/render-ready separation intact
- [ ] Unicode behavior tested
- [ ] BiDi workaround safe
- [ ] font metrics correct
- [ ] wrapping correct

## Glossary
- [ ] deterministic
- [ ] scoped
- [ ] context-aware
- [ ] QA-aware
- [ ] Alex case resolved or explicitly classified

## GUI
- [ ] RTL works
- [ ] LTR works
- [ ] state transitions clean
- [ ] errors visible

## CLI
- [ ] commands correct
- [ ] exit codes meaningful

## E2E
- [ ] real fixture passes
- [ ] repeat stable
- [ ] force works
- [ ] glossary revision works
- [ ] provider change works
- [ ] project isolation works
- [ ] export/reparse works

## Packaging
- [ ] EXE builds
- [ ] EXE runs outside repo cwd
- [ ] resources included
- [ ] dependencies correct

## Quality
- [ ] no known critical/high defects
- [ ] no important silent swallowing
- [ ] docs match reality
- [ ] no unexplained production-critical TODO/FIXME

---

# 40. FINAL REPORT — EXACT STRUCTURE

## 1. Executive Summary
What changed and why.

## 2. Repository Inventory
What was inspected.

## 3. Architecture Before
Actual observed architecture.

## 4. Architecture After
Actual changes.

## 5. Exact Files Changed
Added / modified / deleted.

## 6. Algorithms Improved
For each:
- old behavior
- problem
- new behavior
- complexity
- benchmark

## 7. Bugs Found
For each:
- reproduction
- root cause
- fix
- regression test

## 8. Alex Investigation
Explicitly state why `Alex` remained untranslated and whether it was:
- expected
- fixture issue
- glossary issue
- provider issue
- cache issue
- product bug

## 9. Database / Cache / TM
Changes and rationale.

## 10. Provider System
Changes.

## 11. Arabic Layer
Changes.

## 12. Glossary
Changes.

## 13. QA
Changes.

## 14. GUI / CLI
Changes.

## 15. E2E Matrix
Exact scenarios and results.

## 16. Adversarial Testing
Everything attacked.

## 17. Performance
Actual before/after measurements.

## 18. Packaging
Build and runtime results.

## 19. Security
Issues found/fixed.

## 20. Documentation
Updated files.

## 21. Remaining Known Issues

Classify:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

Do not hide anything.

## 22. Phase 3 Readiness
What interfaces are now ready.

Do NOT implement Phase 3.

## 23. Final Test Counts
Exact command and exact:

```text
passed
failed
skipped
xfail
```

## 24. Final Verification Matrix

Use:

```text
Implemented
Verified offline
Verified integration
Verified E2E
Verified manually
Unverified
Known limitation
```

---

# 41. ABSOLUTE RULES

1. Inspect the entire project.
2. Refactor the project, not one module.
3. Fix root causes.
4. Do not hide bugs.
5. Do not fake verification.
6. Do not change product scope.
7. Do not start Phase 3.
8. Do not destroy original fixtures.
9. Do not expose secrets.
10. Do not commit unless explicitly requested.
11. Preserve canonical translations.
12. Preserve successful current behavior.
13. Improve architecture only when justified.
14. Remove dead/duplicate code where safe.
15. Test after every meaningful refactor cluster.
16. Finish with a complete E2E run.
17. Perform a second self-audit after tests pass.
18. Be brutally honest in the final report.

# FINAL SUCCESS CONDITION

The repository should end this task looking like a project another experienced engineer can inherit and continue developing without asking:

> "Why is this implemented three different ways?"

and without discovering a major architectural or algorithmic defect immediately when Phase 3 begins.

Final target:

```text
Clean architecture
+
Correct algorithms
+
Safe persistence
+
Deterministic cache/TM
+
Robust provider layer
+
Arabic processing
+
Glossary
+
QA
+
RTL GUI
+
Overlay abstraction
+
Real E2E
+
Reliable EXE
+
Strong tests
+
Honest documentation
=
HARDENED ALMURRIB
```
