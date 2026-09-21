# Almurrib — Phase 3 Full Expansion, Integration, Refactor, E2E & UI Overhaul
## Mission: Take the project from a strong Phase 2 foundation to a real multi-engine localization platform

You are the lead architect, senior Python engineer, localization engineer, reverse-engineering engineer, QA engineer, performance engineer, packaging engineer, and UI engineer for **Almurrib (المعرب)**.

This is a **full Phase 3 implementation shift**, not a small feature task.

The user expects you to work A→Z across the repository:
- acquire/evaluate the planned open-source arsenal
- integrate the useful pieces
- build real engine adapters
- implement patch/rebuild/runtime strategies
- refactor the project where integration exposes weaknesses
- redesign the UI into a simple smooth workflow
- run serious E2E tests
- fix bugs and regressions
- harden packaging/security/licensing
- finish with a full self-audit

Do not optimize for a pretty report. Optimize for a working product.

---

# 0. PRODUCT NORTH STAR

The desired workflow becomes:

```text
Drop/select game folder
        ↓
Detect engine
        ↓
Extract
        ↓
Normalize
        ↓
Glossary + context
        ↓
Translate
        ↓
Arabic QA
        ↓
Arabic processing
        ↓
Patch/rebuild OR runtime overlay
        ↓
Test/launch
        ↓
Arabic appears to player
```

The user should no longer need to manually find source files, move translation files, run helper scripts, or understand SQLite internals for normal use.

Automate repetitive work.

Keep manual decisions only where ambiguity or game-specific behavior genuinely requires them.

---

# 1. CURRENT PRODUCT RULE — ENGLISH BASE, ARABIC DISPLAY

This Phase 3 rule is mandatory:

```text
Game base/original locale = English whenever possible
Displayed localization = Arabic
Almurrib UI locale = independent
```

Do NOT assume that a game must add a formal Arabic language entry.

Prefer:

```text
Game says English
    ↓
Almurrib replacement/overlay
    ↓
Player sees Arabic
```

For static games, use the safest file/resource localization method available.

For runtime-capable games, use runtime override/interception where appropriate.

The Ren'Py `ar` mechanism used in the Phase 2 visual test was a test mechanism; do not treat it as the universal product architecture.

---

# 2. WORK THROUGH THE WHOLE PHASE

Follow this order:

```text
Repository reconnaissance
→ tool/license audit
→ architecture plan
→ tool acquisition
→ common adapter/capability layer
→ engine adapters
→ runtime strategies
→ extraction/build/patch
→ translation/QA integration
→ UI overhaul
→ fixtures
→ automated + adversarial + E2E tests
→ refactor after integration
→ packaging
→ final audit
```

Do not stop after the first adapter.

If one dependency cannot be integrated because of:
- license
- maintenance
- platform incompatibility
- unusable API
- excessive technical cost

do NOT fake support.

Document the reason, choose an alternative when possible, and continue the rest of the phase.

---

# 3. GIT SAFETY

Before changes:

```powershell
git status
git diff
git branch --show-current
```

Never:
- reset
- clean destructively
- discard user work
- rewrite history
- auto-commit

At the end:

```powershell
git status
git diff --stat
git diff --check
```

Do not commit unless explicitly requested.

---

# 4. FULL REPOSITORY AUDIT

Inspect the actual current repository, including whatever exists under:

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

Understand:
- Core/domain
- Pipeline/workflow
- Database
- Cache/TM
- Glossary
- QA
- Arabic layer
- Providers
- GUI
- CLI
- Ren'Py
- Browser acceptance fixture
- Packaging

Find duplicate concepts, dead code, temporary code, stale docs, and architecture violations.

---

# 5. COMMON ENGINE ARCHITECTURE

Create/strengthen a capability-driven adapter model.

Conceptually:

```text
EngineDefinition
  id
  display_name
  detector
  extractor
  exporter/builder
  runtime_strategies
  supported_formats
  limitations
```

All engines converge into:

```text
Engine source
→ normalized LocalizationEntry
→ glossary/context
→ translation
→ QA
→ Arabic processing
→ engine-specific output
```

Do NOT scatter engine-specific `if/elif` logic through core translation code.

---

# 6. PHASE 3 ARSENAL TO AUDIT / ACQUIRE

Use the project plan as the source of the planned arsenal.

## Ren'Py
```text
Lattyware/unrpa
Ren'Py built-in translation system
anonymousException/renpy-translator
abse4411/projz_renpy_translation
```

## Unity
```text
K0lb3/UnityPy
nesrak1/UABEA
nesrak1/AssetsTools.NET
SamboyCoding/Cpp2IL
BepInEx/BepInEx
bbepis/XUnity.AutoTranslator
xSh4r103/AnyFontUnity
```

## Unreal
```text
trumank/repak
atenfyr/UAssetAPI
Snoozeds/UnrealLocresEditor
UE4SS-RE/RE-UE4SS
```

## RPG Maker
```text
direct JSON
yexi-by/att
```

## Skyrim / Bethesda
```text
Mutagen-Modding/Mutagen
TES5Edit/TES5Edit
wrye-bash/wrye-bash
```

## Godot / Paradox
```text
Bioruebe/gdsdecomp
khoeos/paradox-translation-toolkit
```

## General / Visual Novel
```text
arcusmaximus/VNTextPatch
satan53x/SExtractor
Artikash/Textractor
HIllya51/LunaTranslator
ramjke/Translumo
kmonkeyhead/MORT
```

## Translation / local inference
```text
ggml-org/llama.cpp
SciSharp/LLamaSharp
OpenNMT/CTranslate2
argosopentech/argos-translate
LibreTranslate
```

## Distribution
```text
velopack/velopack
SignPath
```

For every project decide:

```text
Integrated dependency
External tool/subprocess
Optional tool
Reference only
Rejected
```

Record:
- version/commit
- source
- license
- purpose
- integration method
- limitations

Do not blindly vendor everything.

---

# 7. LEGAL / LICENSE BOUNDARIES

Respect the project plan's licensing notes and verify each actual repository/license file before integration.

Important:
- MIT/Apache/etc.: follow attribution requirements
- GPL/AGPL/LGPL: integrate according to actual license requirements
- fonts: preserve attribution/license
- models: review the exact model license
- no-license/unknown-license source: **do not copy its code**
- `AtomCrafty/UniversalInjectorFramework` was explicitly marked as no-license in the plan: ideas/reference only, no source copying
- do not redistribute proprietary game assets/text as fixtures

Update:

```text
THIRD_PARTY_NOTICES.md
```

---

# 8. UNITY — MAJOR TARGET

Implement a real Unity adapter.

## Detection
Identify:
- Unity version
- Mono vs IL2CPP where practical
- asset/resource structure
- localization indicators

## Extraction
Use the best combination of:
- UnityPy
- UABEA
- AssetsTools.NET
- Cpp2IL

Extract text into common LocalizationEntry records.

Preserve:
- asset/object/source references
- localization keys
- original data required for rebuild

## Build/Patch
Never overwrite original game data directly.

Use a working copy and support rollback.

## Runtime
Where appropriate, use BepInEx as the runtime foundation and investigate XUnity.AutoTranslator compatibility.

Goal:

```text
English base
→ runtime intercept/lookup
→ Arabic
→ display
```

## Fonts
Investigate AnyFontUnity or an equivalent safe project-local font strategy.

Build a tiny Unity E2E fixture.

---

# 9. UNREAL ENGINE

Implement a real Unreal adapter.

Evaluate/integrate:

```text
repak
UAssetAPI
UnrealLocresEditor
UE4SS
```

Support, where practical:
- detection
- `.pak` extraction/rebuild
- localization asset handling
- safe patch/build
- runtime overlay strategy

Do not claim generic Unreal support when only a subset is proven.

Build a synthetic/open fixture.

---

# 10. RPG MAKER

Implement MV/MZ support around the actual JSON data formats.

Use:
- direct JSON where sufficient
- `att` only where it adds real value

Support:

```text
detect
→ extract
→ translate
→ QA
→ write back
→ verify
```

Add a minimal E2E fixture.

---

# 11. BETHESDA / SKYRIM

Evaluate/build an adapter using the planned tools where useful:

```text
Mutagen
TES5Edit
Wrye Bash
```

Support a clearly defined subset first.

Use capability metadata and honest version limitations.

---

# 12. GODOT / PARADOX

Evaluate/build support using:

```text
gdsdecomp
paradox-translation-toolkit
```

Again: support verified formats/versions, not imaginary universal support.

---

# 13. VISUAL NOVELS / GENERAL ENGINES

Primary target:

```text
VNTextPatch
```

because the project plan targets 20+ engine coverage through it.

Secondary tools to evaluate:

```text
SExtractor
Textractor
LunaTranslator
Translumo
MORT
```

Do NOT embed everything into the main executable.

Represent strategies such as:

```text
Static extraction
Memory hook
OCR
Text patch
Runtime overlay
```

and let capabilities choose the path.

---

# 14. TRANSLATION ENGINES

Strengthen local inference and offline translation using the planned stack where justified:

```text
llama.cpp
LLamaSharp (only if needed)
CTranslate2
Argos Translate
LibreTranslate
```

Continue to support:

```text
local-first
+
optional cloud BYO key
```

Do not make the cloud mandatory.

Do not bundle huge model weights into the application automatically.

Support model paths, discovery, capability metadata, and download/setup instructions.

---

# 15. RUNTIME OVERLAY + ADAPTIVE MODE

Turn the Phase 2 overlay abstraction into a real Phase 3 capability system.

Conceptual strategies:

```text
StaticPatchStrategy
GeneratedLocalizationStrategy
RuntimeHookStrategy
OCRStrategy
```

Runtime requirements:
- English fallback
- Arabic lookup
- local cache
- safe failure fallback
- stable source/key matching
- optional observed-text collection
- no automatic upload

Adaptive mode:

```text
Play
→ untranslated text observed
→ store locally
→ translate later
→ next run shows Arabic
```

Keep collection opt-in and local-first.

---

# 16. FONT / ARABIC RENDERING ACROSS ENGINES

Use the Phase 2 Arabic layer as the shared authority.

Do not duplicate Arabic handling inside each adapter.

Each adapter should only provide:
- text representation
- font/resource hook
- render strategy
- engine-specific constraints

The core Arabic layer continues to own:

```text
normalize
reshape
BiDi
wrap
metrics
QA
```

Preserve canonical logical text.

---

# 17. GUI REDESIGN — MAKE IT SIMPLE

The current UI should be reviewed from scratch as a user workflow.

Goal:

```text
Drop/select game
→ Detect
→ Arabic
→ Provider/model
→ Start
→ Progress
→ QA summary
→ Build/patch
→ Launch/test
```

Default UI must NOT expose:
- SQLite
- cache internals
- raw paths everywhere
- provider request JSON
- low-level engine files

unless Advanced mode is opened.

Create:

## Simple mode
```text
Game
Language
Provider/Model
Start
```

## Advanced mode
```text
Glossary
QA
Cache/TM
Provider settings
Output
Runtime strategy
Engine options
Logs
Diagnostics
```

Make the interface:
- smooth
- uncluttered
- beginner-friendly
- RTL-capable
- responsive
- clear about errors
- clear about progress

Prefer the project's long-term Tauri + React direction if the current architecture can support it without compromising the core. If a UI rewrite is needed, preserve the Python core behind a stable service boundary.

---

# 18. AUTOMATED DETECTION UI

The main UI should automatically show:

```text
Detected engine: Unity
Version: ...
Build type: IL2CPP
Capabilities:
  Static patch ✓
  Runtime overlay ✓
  Arabic font injection ✓
```

Unsupported situations should show a clear explanation and next action.

---

# 19. PROGRESS / OBSERVABILITY

Show real stages:

```text
Detecting...
Extracting 142 / 850
Translating 430 / 850
QA...
Building...
Done
```

Also summarize:

```text
Translated
Cache/TM reused
Warnings
Errors
Skipped
```

Do not hide failures behind a generic "finished".

---

# 20. AUTOMATE MANUAL WORK

The target workflow should eliminate most of the current manual steps.

Instead of:

```text
find source
copy file
run helper
move output
rename directory
patch manually
```

the product should do:

```text
select game
→ detect
→ localize
→ build/patch
```

Use the existing database internally without forcing the user to understand it.

---

# 21. DATA / CACHE / TM AT PHASE 3 SCALE

Prepare storage for large games.

Audit/add support for:
- engine ID
- adapter version
- game identity
- project scope
- language pair
- glossary revision
- provider/model
- runtime/static strategy
- source fingerprint
- localization revision

Add the right indexes.

Test larger datasets.

---

# 22. SECURITY

Treat games and game archives as untrusted input.

Audit/fix:
- traversal
- absolute paths
- symlinks
- archive extraction
- arbitrary writes
- unsafe subprocess execution
- DLL/plugin loading
- temp file cleanup
- secret leakage

Never auto-execute arbitrary files from a game directory without explicit user action.

---

# 23. FULL E2E FIXTURE MATRIX

Create small legal fixtures for:

```text
Ren'Py
Unity
Unreal
RPG Maker
VN/VNTextPatch
Godot (where practical)
Bethesda (where practical)
Paradox (where practical)
```

Use synthetic/open-source/redistributable fixtures.

Each fixture should test:

```text
detect
extract
speaker/name
choices
placeholders
markup where supported
mixed scripts
glossary
translation
QA
Arabic processing
export/rebuild
reparse
runtime overlay if supported
```

For anything unavailable, state:

```text
UNVERIFIED
```

never fake it.

---

# 24. FULL E2E MATRIX

Run:

## Clean
```text
detect
→ extract
→ translate
→ QA
→ persist
→ build
→ reparse/load
```

## Second run
Expected:
```text
stable
cache/TM hits
no unnecessary provider work
```

## Force
Expected:
```text
policy-compliant real reprocessing
```

## Glossary change
Expected:
```text
relevant invalidation
unrelated stability
```

## Provider/model change
Expected:
```text
no incompatible stale reuse
```

## Project isolation
Expected:
```text
A cannot contaminate B
```

## Partial failure
Expected:
```text
successful items survive
failed items recover
```

## Runtime
Expected:
```text
English fallback if Arabic unavailable
Arabic display when translation exists
```

---

# 25. ADVERSARIAL TESTING

Attack:
- malformed assets
- missing files
- duplicate IDs
- huge files
- broken archives
- provider timeouts
- malformed provider output
- invalid placeholders
- markup corruption
- Unicode edge cases
- mixed scripts
- missing glyphs
- bad fonts
- invalid paths
- interrupted builds
- repeated runs
- source updates
- game updates
- huge glossary
- many projects
- two projects with same relative paths

For every real bug:

```text
reproduce
→ regression test
→ fix root cause
→ targeted tests
→ full suite
```

---

# 26. PERFORMANCE / SCALING

Benchmark:

```text
1,000 entries
10,000 entries
50,000 entries
100,000 where practical
```

Measure:
- detection
- extraction
- glossary
- translation preparation
- QA
- DB
- export
- runtime lookup
- font metrics
- patch/build
- repeated runs

Profile real bottlenecks.

Do not optimize only microbenchmarks.

---

# 27. FULL REFACTOR AFTER INTEGRATION

After engine integrations are working, perform another A→Z architecture review.

Consolidate:
- duplicate adapter logic
- shared resource handling
- common patch/build interfaces
- runtime strategies
- error handling
- logging
- configuration
- UI state
- packaging

Do not leave prototype code just because it works.

---

# 28. PACKAGING / EXE / DISTRIBUTION

Build:

```powershell
.\.venv\Scripts\python build_exe.py
```

Run from a different working directory.

Verify:
- imports
- fonts
- glossary
- i18n
- DB
- provider definitions
- adapters
- optional tools
- resource paths

Evaluate:

```text
Velopack
```

for installation/updating where practical.

Prepare signing through the planned SignPath route if practical.

Never claim signing unless actually performed.

---

# 29. DOCUMENTATION

Create/update:

```text
docs/PHASE3_ARCHITECTURE.md
docs/ENGINE_SUPPORT.md
docs/UNITY.md
docs/UNREAL.md
docs/RPGMAKER.md
docs/VN.md
docs/RUNTIME_OVERLAY.md
docs/TOOLS_AND_LICENSES.md
docs/PHASE3_E2E.md
docs/TROUBLESHOOTING.md
docs/UI_WORKFLOW.md
```

For each engine document:

```text
Supported versions
Detection
Extraction
Translation
Build/Patch
Runtime
Arabic font strategy
Limitations
Verification status
```

Clearly label:

```text
VERIFIED
PARTIALLY VERIFIED
EXPERIMENTAL
UNVERIFIED
UNSUPPORTED
```

---

# 30. PHASE 4 FIREWALL

Do NOT implement:
- community TMX/XLIFF hosting/synchronization
- GitHub community sharing
- contributor infrastructure
- Arabic LoRA training
- translation marketplace
- centralized mandatory server

Only prepare extension points.

---

# 31. DEFINITION OF DONE

The task is complete only when:

## Core
- [ ] engine capability architecture stable
- [ ] shared pipeline remains authoritative
- [ ] cache/TM/project isolation robust
- [ ] errors are explicit

## Ren'Py
- [ ] existing support remains stable
- [ ] improvements integrated only where justified

## Unity
- [ ] detect
- [ ] extract
- [ ] normalize
- [ ] translate
- [ ] QA
- [ ] patch/build
- [ ] runtime strategy where supported
- [ ] Arabic font strategy
- [ ] E2E fixture

## Unreal
- [ ] detect
- [ ] extract
- [ ] localization
- [ ] patch/build
- [ ] runtime where supported
- [ ] E2E fixture

## RPG Maker
- [ ] detect
- [ ] extract
- [ ] write back
- [ ] E2E

## VN
- [ ] broad strategy
- [ ] VNTextPatch integration where justified
- [ ] supporting tools evaluated
- [ ] E2E fixtures

## Other engines
- [ ] supported subset documented honestly
- [ ] adapters tested

## Runtime
- [ ] overlay strategies
- [ ] fallback
- [ ] local cache
- [ ] adaptive/local observation path where supported

## UI
- [ ] simple mode
- [ ] advanced mode
- [ ] RTL/LTR
- [ ] clear progress
- [ ] clear errors
- [ ] automatic engine detection
- [ ] reduced manual steps

## Packaging
- [ ] EXE
- [ ] resource resolution outside repo cwd
- [ ] release packaging where practical

## E2E
- [ ] multi-engine fixtures
- [ ] regression tests
- [ ] adversarial tests
- [ ] performance tests
- [ ] manual acceptance plan

---

# 32. FINAL REPORT — EXACT STRUCTURE

## 1. Executive Summary
## 2. Phase 3 Capabilities Completed
## 3. Full Third-Party Arsenal
For each:
- status
- version/commit
- license
- integration method
- limitations

## 4. Architecture Before
## 5. Architecture After
## 6. Engine Support Matrix

Use:

```text
Engine | Detect | Extract | Translate | Build/Patch | Runtime | Arabic | E2E
```

## 7. Runtime Overlay
## 8. GUI Redesign
## 9. CLI
## 10. Bugs Found
For each:
- reproduction
- root cause
- fix
- regression

## 11. Algorithms / Performance
Before/after where meaningful.

## 12. Adversarial Testing
## 13. Security
## 14. Licensing
## 15. Packaging / EXE
## 16. Documentation
## 17. Remaining Issues

Use:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

## 18. Phase 4 Readiness
## 19. Final Test Counts
Exact:

```text
passed
failed
skipped
xfail
```

## 20. Final Verification Matrix

For every major capability:

```text
IMPLEMENTED
AUTOMATED VERIFIED
INTEGRATION VERIFIED
E2E VERIFIED
MANUALLY VERIFIED
EXPERIMENTAL
UNVERIFIED
UNSUPPORTED
```

---

# 33. ABSOLUTE RULES

1. Inspect the whole repository.
2. Do the complete Phase 3 scope, not a token subset.
3. Do not stop at "downloaded dependencies".
4. Do not fake support.
5. Do not copy unlicensed code.
6. Preserve the original games and create working copies.
7. Keep cloud optional.
8. Keep local-first behavior.
9. Preserve canonical translation data.
10. Do not hide errors.
11. Do not silently swallow important failures.
12. Do not start Phase 4.
13. Do not auto-commit.
14. Perform a second refactor after integrations.
15. Finish with full E2E, adversarial, performance, and packaging tests.
16. Be explicit about every unverified capability.

# FINAL SUCCESS CONDITION

The final experience should feel like a real localization platform:

```text
Select/drop game
      ↓
Automatic detection
      ↓
Extract
      ↓
Glossary + Translation
      ↓
Arabic QA
      ↓
Arabic processing
      ↓
Static patch OR runtime overlay
      ↓
Test/launch
      ↓
Arabic displayed
```

Target product experience:

> **Drop a game → Almurrib figures out what it is → does the localization work automatically → shows what succeeded/failed → builds or overlays the Arabic → lets the user test it.**

Build the engineering required to make that true.
