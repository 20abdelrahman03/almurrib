# Almurrib — Zero-State Repository Refactor, Cleanup, Bug Sweep, Algorithm Audit & E2E Hardening
## Mission: Leave the Repository Clean, Coherent, Tested, and Ready for Heavy Phase 3/Unity Work

You are the **lead maintainer, software architect, Python engineer, QA engineer, performance engineer, build/release engineer, localization engineer, and repository janitor** for **Almurrib (المعرب)**.

The project is about to enter a very heavy period:
- Unity integration
- real game experiments
- many fixtures
- large assets
- write-back experiments
- runtime tests
- multiple external tools
- repeated E2E runs
- many bug fixes and regressions

Before that begins, the repository must be put into a **clean zero-state engineering baseline**.

This task is NOT about adding a major new feature.

This task is:

> **Create a safe Git checkpoint first, inspect every file, remove obsolete/duplicate/experimental leftovers, organize documentation, repair all discovered bugs, review important algorithms, remove wasteful complexity and token waste, close stale rabbit holes, run exhaustive static + dynamic + E2E validation, and leave the repository clean enough that future heavy work starts from a trustworthy baseline.**

The target is not "everything looks nice."

The target is:

```text
clean repository
+
clear architecture
+
no unexplained duplicates
+
no stale code
+
no broken imports/syntax
+
no obvious algorithm bugs
+
no stale documentation contradictions
+
no accidental generated garbage
+
no unexplained TODO rabbit holes
+
deterministic tests
+
working E2E
+
safe Git checkpoint
=
ZERO-STATE ALMURRIB
```

---

# 0. VERY IMPORTANT — CREATE A GIT CHECKPOINT FIRST

Before deleting, moving, renaming, or refactoring anything:

```powershell
git status
git diff
git branch --show-current
git log -5 --oneline
```

Then create a **checkpoint commit** containing the current working state.

Use a clear message such as:

```text
chore: pre-refactor checkpoint
```

This checkpoint is explicitly required by this task.

Before creating it:
- do not alter source files
- do not format files
- do not clean files
- do not "fix" anything

The checkpoint must represent the state **before** the cleanup/refactor.

After the checkpoint exists:
- record its commit hash
- record the working tree status
- continue the refactor

If there are unrelated uncommitted user changes, DO NOT silently absorb or destroy them.
Clearly identify them and preserve them safely.

---

# 1. ABSOLUTE SAFETY RULES

1. Never delete an unknown file just because it "looks unused".
2. Never overwrite user-owned work without evidence.
3. Never reset the repository after the checkpoint.
4. Never rewrite history.
5. Never force-push.
6. Never commit every tiny fix.
7. The initial checkpoint commit is required; later commits are optional unless explicitly requested.
8. Preserve original game fixtures unless they are confirmed disposable/generated.
9. Do not delete generated artifacts until you know how they are generated and whether they belong in Git.
10. Do not remove a dependency until all import/use paths are verified.
11. Do not remove documentation until its ownership/replacement is understood.
12. Do not silently downgrade behavior just to make tests green.
13. Never hide a bug by weakening a test.
14. Never solve a bug by deleting the failing code without understanding why it exists.
15. Never expand scope indefinitely.

---

# 2. SECOND CHECKPOINT — INVENTORY BEFORE DELETION

After the Git checkpoint, perform a complete repository inventory.

Inspect the actual repository tree, not just expected folders.

At minimum inspect:

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
*.bat
*.ps1
*.py
```

Also inspect hidden/config files relevant to builds.

Create an internal inventory with categories:

```text
Production source
Test source
Fixture
Generated artifact
Build artifact
Documentation
Experimental code
Temporary code
Deprecated code
Unknown
```

Do not delete `Unknown` items yet.

---

# 3. REPOSITORY MAP

Build an accurate repository map.

Determine:

```text
Entry points
Core modules
Persistence
Providers
Arabic layer
Engine adapters
CLI
GUI
Tools
Tests
Fixtures
Docs
Build/package
Generated outputs
```

For each directory determine:
- purpose
- owner/responsibility
- whether it is production or test-only
- whether it should remain
- whether it is in the correct location

Identify files that are obviously in the wrong directory.

---

# 4. DETECT DUPLICATE / LEGACY IMPLEMENTATIONS

Search for multiple implementations of the same concept.

Specifically hunt for:

- duplicate LocalizationEntry models
- duplicate QA engines
- duplicate placeholder parsing
- duplicate Arabic processing
- duplicate glossary matching
- duplicate path helpers
- duplicate provider interfaces
- duplicate provider error mapping
- duplicate model representations
- duplicate config parsing
- duplicate workflow orchestration
- duplicate Ren'Py parsing/export
- duplicate font logic
- duplicate cache/TM logic
- duplicate GUI business logic
- duplicate CLI business logic
- duplicate browser-test converters
- duplicate test utilities

For every duplicate:

```text
Identify canonical implementation
→ classify old implementation
→ migrate callers
→ delete/quarantine obsolete implementation
→ add regression test
```

Do not keep "just in case" duplicate production implementations.

---

# 5. OLD / STALE / DEAD CODE SWEEP

Search aggressively for:

```text
TODO
FIXME
HACK
XXX
DEPRECATED
TEMP
temporary
legacy
unused
old
backup
copy
_v2
_new
_old
```

Also search for:

```text
pass
except Exception
return None
silent fallback
dead branches
unreachable code
commented-out code blocks
debug prints
temporary logging
hard-coded local paths
```

For each finding classify:

```text
KEEP — still valid
FIX — actual defect
REFACTOR — active but poor
DELETE — confirmed obsolete
ARCHIVE — historical/reference value
DOCUMENT — intentional limitation
```

Do not leave unexplained production TODOs in critical paths.

---

# 6. "RABBIT HOLE" CONTROL

This is mandatory.

The project is about to become much larger, so prevent endless side quests.

Create a rule:

> **Every investigation must have a clear question, evidence, stopping condition, and outcome.**

For every rabbit hole found in code/docs/issues:

```text
Question
Why it exists
Evidence
Decision
Action
```

Decisions may be:

```text
Fix now
Defer explicitly
Reject
Document limitation
```

Do NOT:
- spend unlimited time exploring unrelated libraries
- redesign working code without evidence
- chase hypothetical edge cases with no user impact
- add libraries just because they exist
- implement future-phase features during cleanup

Create a short document if useful:

```text
docs/DECISIONS.md
```

or merge into an existing architecture/decision document.

---

# 7. TOKEN / COMPLEXITY WASTE AUDIT

The project will be used heavily with AI coding agents.

Audit the repository for unnecessary token/code waste.

Look for:

- gigantic duplicated prompts embedded in source
- repeated schemas
- repeated provider instructions
- duplicated constants
- generated files committed unnecessarily
- verbose logs with no value
- duplicated documentation
- giant fixture data when smaller data would prove the same invariant
- duplicate test setup
- helper functions that only wrap one line without adding meaning
- multiple similar serialization formats
- repeated tool instructions
- redundant compatibility layers

The goal is:

> **Reduce noise without reducing correctness.**

Do not aggressively compress readable code.

Prefer:
- shared fixtures
- shared factories
- shared schemas
- concise diagnostics
- centralized constants
- reusable test helpers

---

# 8. DOCUMENTATION REORGANIZATION

This is a major deliverable.

Inspect every `.md`, `.mdx`, text-based guide, report, and planning document.

Then establish a clean documentation structure.

Prefer something like:

```text
docs/
├── README.md
├── ARCHITECTURE.md
├── DEVELOPMENT.md
├── TESTING.md
├── TROUBLESHOOTING.md
├── CLI.md
├── GUI.md
├── PROVIDERS.md
├── ARABIC_LAYER.md
├── QA.md
├── GLOSSARY.md
├── FONTS.md
├── OVERLAY.md
├── ENGINES/
│   ├── RENPY.md
│   ├── UNITY.md
│   └── ...
├── PHASES/
│   ├── PHASE1.md
│   ├── PHASE2.md
│   └── PHASE3.md
├── DECISIONS.md
├── THIRD_PARTY.md
└── reports/
    ├── ...
```

Do NOT blindly create this exact tree if the project already has a better structure.

Important rules:

### Canonical docs
Each concept should have ONE authoritative documentation location.

### Historical reports
Old progress reports and AI-generated milestone reports should not clutter the root.
Move them into a clearly labeled historical/report directory if still useful.

### Temporary prompt files
Keep implementation prompts out of production docs unless they are intentionally part of project history.

### Generated reports
Clearly separate generated artifacts from maintained documentation.

### Broken links
After moving docs, repair all relative links.

---

# 9. DOCUMENTATION TRUTH AUDIT

Cross-check:

```text
README
docs
CLI help
GUI behavior
code
tests
```

Find contradictions such as:

```text
docs say supported
code says experimental
tests do not verify it
```

Normalize terminology.

Use explicit status labels:

```text
IMPLEMENTED
VERIFIED
E2E VERIFIED
MANUALLY VERIFIED
EXPERIMENTAL
UNVERIFIED
UNSUPPORTED
DEPRECATED
```

Never let old reports silently look like current truth.

---

# 10. SOURCE CODE STRUCTURE CLEANUP

Review package structure.

Ensure:

- imports follow clear direction
- no accidental circular dependencies
- no GUI imports inside core business logic
- no provider-specific code inside generic domain models
- no engine-specific rules scattered through translation code
- no test-only dependencies in runtime paths
- no tools module secretly becomes production core

If a file is doing too many unrelated jobs, split it only when the boundary is real.

Do not create dozens of tiny modules without reason.

---

# 11. IMPORT / SYNTAX / BASIC HEALTH SWEEP

Before deep functional testing, run strict basic checks.

At minimum, where appropriate:

```powershell
python -m compileall
pytest
```

Also run the project's configured lint/type/static checks if they exist.

If tools are missing:
- inspect `pyproject.toml`
- use existing project tooling
- do not install a huge new ecosystem just to satisfy aesthetics

Find and fix:

- syntax errors
- import errors
- missing names
- wrong module paths
- circular imports
- dead imports
- undefined variables
- mismatched signatures
- malformed configuration
- encoding problems

---

# 12. STATIC CODE QUALITY SWEEP

Review for:

- mutable default arguments
- accidental shared state
- global caches without scope
- inappropriate singletons
- path assumptions
- broad exception handling
- hidden side effects
- overly complex functions
- deeply nested conditionals
- duplicated constants
- inconsistent naming
- impossible states
- implicit type coercion
- Python boolean/int traps
- resource leaks
- file handles not closed
- transactions not committed/rolled back
- subprocesses not cleaned up

Fix real defects.

Do not refactor code merely to make it aesthetically different.

---

# 13. ALGORITHM AUDIT — EVERY IMPORTANT ALGORITHM

Do a conceptual review of all important algorithms.

At minimum inspect:

### Glossary
- matching
- overlap resolution
- aliases
- boundaries
- forbidden terms
- normalization
- complexity

### Cache/TM
- keys
- scope
- invalidation
- provenance
- stale results

### QA
- rule ordering
- severity
- false positives/negatives
- deterministic behavior

### Arabic
- normalization
- masking
- shaping
- BiDi
- wrapping
- metrics

### Translation
- batching
- fallback
- retries
- duplicate requests
- cache reuse
- context assembly

### Extraction
- candidate detection
- deduplication
- stable identifiers
- source references

### Export/write-back
- deterministic ordering
- duplicate prevention
- round-trip stability
- corruption prevention

For each important algorithm ask:

```text
What is the input?
What is the output?
What are the invariants?
What is the worst case?
What is the complexity?
What can go wrong?
What happens on malformed input?
Is it deterministic?
```

---

# 14. PERFORMANCE AUDIT

Find unnecessary O(N²), repeated parsing, repeated regex compilation, repeated font loading, repeated database queries, unnecessary provider calls, and duplicated serialization.

Benchmark meaningful workloads:

```text
100
1,000
10,000
50,000
100,000 where practical
```

Measure important paths.

For every real optimization:

```text
Before
→ bottleneck
→ change
→ after
→ proof that behavior stayed correct
```

Do not optimize theoretical micro-costs at the expense of readability.

---

# 15. STORAGE / DATABASE CLEANUP

Audit:
- migrations
- indexes
- foreign keys
- unique constraints
- project scoping
- glossary revision
- provider/model provenance
- cache/TM scope
- WAL
- transactions
- connection lifecycle
- stale/obsolete entries

Verify:
- migrations from older DBs work
- duplicate records cannot accumulate accidentally
- project A cannot reuse project B's translations
- glossary revisions invalidate the correct entries
- force runs really reprocess
- repeated runs are stable

---

# 16. PROVIDER CLEANUP

Audit all providers.

Normalize:

```text
request
response
errors
timeouts
retry
rate limits
model discovery
capabilities
provenance
logging
```

Ensure secrets never reach:
- logs
- exceptions
- generated reports
- fixtures
- Git
- browser debug panels

Remove obsolete provider definitions and stale model catalogs.

Do not keep dead provider code "just in case."

---

# 17. GUI CLEANUP

Make the GUI boringly reliable.

Fix:
- stale state
- duplicate event handlers
- widgets rebuilding incorrectly
- broken clipboard behavior
- path bugs
- error reporting
- provider/model refresh
- RTL switching
- progress state
- disabled/enabled buttons
- settings persistence
- output path state

The GUI must not implement business logic independently of the core.

Keep UI simple.

---

# 18. CLI CLEANUP

Audit all commands and ensure:

```text
help
detect
extract
inspect
db
translate
export
localize
glossary
```

have:
- coherent options
- correct exit codes
- useful errors
- safe paths
- deterministic output

Remove obsolete commands only after verifying there are no real callers.

---

# 19. REN'PY CLEANUP

Preserve the proven working flow.

Verify:
- extraction
- speaker handling
- choices
- translation blocks
- export
- reparse
- visual test assets
- original file safety

Do not break Phase 1 while cleaning.

---

# 20. UNITY PREPARATION CHECK

Because heavy Unity work is next, explicitly review the Unity implementation even if the refactor is not the Unity milestone itself.

Check:

- current detection
- extraction architecture
- write-back interfaces
- capability model
- tool boundaries
- asset references
- working-copy model
- rollback
- E2E fixture
- external tool management

Do NOT add random Unity features during cleanup.

The objective is:

> **Make the Unity work easier and safer to continue.**

---

# 21. TEST SUITE AUDIT

Do not trust the test count.

Classify:

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
```

Remove:
- duplicate tests
- tests that only repeat another assertion
- tests testing implementation details unnecessarily
- obsolete tests

Add missing tests for:
- real bugs
- boundary conditions
- serialization
- migrations
- path handling
- GUI critical flows
- EXE resource resolution
- algorithm invariants

The final suite should be smaller or larger based on quality, not vanity count.

---

# 22. BUG-HUNTING SWEEP

Search the entire codebase for likely bug patterns:

```text
except Exception
pass
TODO
FIXME
HACK
assert used for user input
bool/int comparisons
mutable defaults
None handling
path joins
string replacement
regex without boundaries
unclosed files
uncommitted transactions
missing rollback
silent fallback
```

Also attack with malformed inputs.

Every genuine bug:

```text
reproduce
→ regression test
→ fix
→ targeted tests
→ full suite
```

---

# 23. RABBIT-HOLE CLOSURE

The task must explicitly close old investigation loops.

Find:
- TODO investigations that no longer matter
- "research later" notes
- abandoned tooling experiments
- duplicate provider research
- stale GitHub links
- old model experiments
- discarded integration attempts
- half-implemented features

For each:

```text
close
archive
delete
document
defer with reason
```

Do not leave dozens of dangling "maybe later" paths in production code.

---

# 24. GENERATED / TEMPORARY FILE CLEANUP

Find:

```text
__pycache__
.pyc
dist/
build/
temporary outputs
logs
test databases
browser outputs
generated localization files
local API artifacts
```

Determine what should:
- be gitignored
- remain as a reproducible fixture
- move under a test/artifacts directory
- be deleted

Do not delete required test fixtures.

Update `.gitignore` if necessary.

---

# 25. PATH / WINDOWS ROBUSTNESS

Verify:

- spaces
- Arabic paths
- non-ASCII paths
- different working directories
- absolute paths
- relative paths
- temp directories
- EXE execution outside repo

No code may assume:

```text
current working directory == repository root
```

---

# 26. PACKAGING AUDIT

Build:

```powershell
.\.venv\Scripts\python build_exe.py
```

Then launch the EXE from another directory.

Verify:
- imports
- fonts
- glossary
- i18n
- database
- providers
- configs
- resources
- path resolution

Fix packaging-specific bugs.

---

# 27. FULL E2E BASELINE

Before declaring cleanup complete, run a full end-to-end baseline.

At minimum:

## Ren'Py
```text
detect
→ extract
→ translate
→ QA
→ persist
→ export
→ reparse
```

## Browser Phase 2 fixture
```text
English
→ Arabic
→ overlay
→ glossary
→ QA
```

## Unity current fixture
Run whatever Unity flow is already genuinely supported.

Do not invent support.

---

# 28. REPETITION / IDEMPOTENCY

Repeat important workflows.

For every repeated run ask:

```text
Did unnecessary translation happen?
Did database rows duplicate?
Did output change without input changes?
Did QA flags duplicate?
Did files change byte-for-byte?
Did caches behave correctly?
```

Where stability is expected:

```text
run(run(project)) == stable state
```

---

# 29. FULL SELF-AUDIT AFTER EVERYTHING PASSES

After all tests are green:

STOP.

Perform a second review as if you were a new senior maintainer.

Specifically search for:

- accidental coupling
- duplicated architecture
- dead code
- stale docs
- generated garbage
- dangerous cleanup
- hidden errors
- silent fallbacks
- wasted tokens
- redundant abstractions
- complexity spikes
- performance regressions
- packaging assumptions
- future-phase leakage

Fix any genuine issue discovered.

Then rerun the full relevant suite.

---

# 30. ZERO-STATE DEFINITION

The repository should reach this state:

### Files
- [ ] no unexplained duplicate source files
- [ ] no obsolete production modules
- [ ] no stray generated files
- [ ] no random reports in source directories
- [ ] no temporary scripts masquerading as production tools
- [ ] docs organized
- [ ] fixture data clearly separated
- [ ] generated artifacts clearly separated

### Code
- [ ] no known syntax/import errors
- [ ] no known high-impact logic bugs
- [ ] no obvious dead code
- [ ] no unexplained broad exception handling
- [ ] no duplicate core implementations
- [ ] algorithms have documented invariants where useful

### Tests
- [ ] full suite passes
- [ ] integration tests pass
- [ ] E2E baseline passes
- [ ] regression tests cover found bugs
- [ ] packaging test passes
- [ ] repeated-run test passes

### Database
- [ ] migrations work
- [ ] project isolation works
- [ ] cache/TM stable
- [ ] no accidental duplication

### Documentation
- [ ] one canonical doc per major concept
- [ ] historical reports separated
- [ ] links repaired
- [ ] docs match actual code

### Git
- [ ] pre-refactor checkpoint commit exists
- [ ] final working tree reviewed
- [ ] no accidental deletions
- [ ] no accidental generated artifacts

---

# 31. FINAL REPORT — EXACT STRUCTURE

## 1. Pre-Refactor Git Checkpoint
Include:
```text
commit hash
branch
initial status
```

## 2. Repository Inventory
What was inspected.

## 3. Files Removed
For every deletion:
- path
- why obsolete
- replacement if any
- proof it was safe

## 4. Files Moved / Reorganized
Before → after.

## 5. Documentation Reorganization
All docs moved/merged/archived.

## 6. Architecture Before
Observed architecture.

## 7. Architecture After
Final architecture.

## 8. Algorithms Reviewed
For each important algorithm:
- old behavior
- issue
- new behavior
- complexity
- verification

## 9. Bugs Found and Fixed
For each:
- reproduction
- root cause
- fix
- regression test

## 10. Rabbit Holes Closed
What was removed/deferred/archived and why.

## 11. Performance
Meaningful before/after numbers.

## 12. Database / Cache / TM
Changes and verification.

## 13. GUI / CLI
Changes and verification.

## 14. Packaging
Build and EXE test.

## 15. E2E Baseline
Exact scenarios run.

## 16. Test Results
Exact:
```text
passed
failed
skipped
xfail
```

## 17. Remaining Issues
Do not hide anything.

Classify:
```text
CRITICAL
HIGH
MEDIUM
LOW
```

## 18. Unity Readiness
What cleanup prepared for the upcoming Unity-heavy phase.

## 19. Final Repository State
Explain why the repository is now a clean baseline.

---

# 32. ABSOLUTE RULES

1. Create the Git checkpoint FIRST.
2. Never delete before understanding.
3. Never hide bugs.
4. Never weaken tests to get green.
5. Never replace user work with assumptions.
6. Never leave stale documentation pretending to be current.
7. Never keep duplicate production implementations without a clear reason.
8. Never start a new rabbit hole without a stopping condition.
9. Never install a giant dependency just for cosmetic reasons.
10. Never expose secrets.
11. Never commit generated garbage.
12. Preserve canonical translations.
13. Preserve successful existing behavior.
14. Fix root causes.
15. Add regressions for real bugs.
16. Refactor carefully, then rerun E2E.
17. Perform a second audit after tests pass.
18. Do not start unrelated future-phase features.
19. The goal is a trustworthy clean baseline for heavy Unity/Phase 3 experimentation.
20. Be brutally honest about anything that remains.

# FINAL SUCCESS CONDITION

The final repository should feel like:

```text
Not a pile of experiments
        ↓
A clean engineering project
        ↓
One canonical implementation per concept
        ↓
One canonical place for each document
        ↓
Clear production/test/generated boundaries
        ↓
Known-good Git checkpoint
        ↓
Strong algorithms
        ↓
Strong tests
        ↓
Reliable E2E
        ↓
Ready for heavy Unity work
```

Do the cleanup deeply enough that the next major Unity phase can focus on hard engine problems instead of wasting time on:
- missing parentheses
- broken imports
- stale files
- duplicated implementations
- wrong paths
- cache contamination
- bad algorithms
- silent exceptions
- obsolete scripts
- documentation chaos
- token-wasting dead code
- old experiments
- avoidable rabbit holes
'''
out = Path('/mnt/data/almurrib_zero_state_full_refactor_prompt.md')
out.write_text(prompt, encoding='utf-8')
print(out)
print(out.stat().st_size)
