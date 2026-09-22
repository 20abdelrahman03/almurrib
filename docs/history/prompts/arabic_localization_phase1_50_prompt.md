# Prompt — Arabic Open-Source Game Localization System
## Mission: Understand the Full Vision and Implement the First 50% of Phase 1

You are the lead software engineer helping build a serious, long-lived, open-source Arabic game localization ecosystem.

Your job in this task is **NOT** to build the whole project.
Your job is to:

1. Fully understand the project's philosophy and architecture.
2. Translate that understanding into a clean technical foundation.
3. Implement only the **first 50% of Phase 1**.
4. Leave the remaining 50% of Phase 1 clearly separated and ready for the next step.
5. Avoid premature work on later phases unless it is required to keep the current foundation clean.

---

# 1. Project Vision

We are building an **open-source Arabic game localization ecosystem**, not just a translator.

The long-term goal is to create a reusable system that can take a real game, understand how its text is stored, extract the translatable content, translate it, validate the result, process Arabic correctly, and put the translation back into the game.

The project is inspired by the ecosystem approach used by projects such as:

- GalTransl
- LunaTranslator
- VNTextPatch
- Textractor
- engine-specific modding and extraction tools

The key lesson is:

> The valuable thing is not one giant tool. The valuable thing is a modular ecosystem where extraction, translation, QA, Arabic processing, reinjection, and runtime support work together.

This project should therefore be designed as infrastructure that can survive beyond its original author.

---

# 2. Core Philosophy

The project must follow these principles:

### Open Source First
The project should remain open and reusable by the community.

### Local First
Local execution is the default whenever practical.

There should be no mandatory project-owned server.

User data should not be uploaded anywhere by default.

### Cloud Optional
Cloud AI providers may be supported through **BYO Key (Bring Your Own Key)**.

The user supplies their own API key.

### Opt-In Sharing
Translation memories, glossaries, and localization resources may be shared by users, but sharing must be opt-in.

Open formats such as TMX/XLIFF should be preferred for shared translation data.

### Long-Term Maintainability
The system should be modular, documented, testable, and understandable by another developer.

Do not create unnecessary coupling.

Do not build everything into one giant application class.

### Reuse Existing Open Source
Do not reinvent mature tools when a suitable open-source project already exists.

Instead, integrate them through clean adapters or interfaces.

Examples from the project research include:

- UnityPy
- UABEA
- AssetsTools.NET
- Cpp2IL
- BepInEx
- repak
- UAssetAPI
- UE4SS
- VNTextPatch
- llama.cpp
- CTranslate2
- Argos Translate
- Velopack

These projects are **building blocks**, not the entire product.

### Our Value Is the Integration Layer
The project should add real value through:

- the common localization pipeline
- the normalized intermediate representation
- translation memory
- glossary handling
- QA rules
- Arabic-specific processing
- engine adapters
- user workflow
- reproducibility
- packaging and maintainability

---

# 3. Long-Term Architecture

The intended high-level architecture is:

```text
┌─────────────────────────────────────────────────────────────┐
│  UI — Tauri + React (Full RTL)                              │
├─────────────────────────────────────────────────────────────┤
│  Core — Our Code                                            │
│  Pipeline • Translation Memory • QA • Glossary • Cache      │
├─────────────────────────────────────────────────────────────┤
│  Arabic Layer — Our Code                                    │
│  Reshaping • BiDi • Fonts • Word Wrapping • RTL             │
├─────────────────────────────────────────────────────────────┤
│  Engine Adapters                                             │
│  Ren'Py • Unity • Unreal • RPG Maker • Godot • ...          │
├─────────────────────────────────────────────────────────────┤
│  Runtime Injection                                           │
│  BepInEx • UE4SS • Plugins                                   │
├─────────────────────────────────────────────────────────────┤
│  Translation Providers                                        │
│  Local (llama.cpp) • Optional Cloud (BYO Key)               │
└─────────────────────────────────────────────────────────────┘
```

The long-term pipeline is:

```text
1. Detect engine
2. Unpack / access game resources
3. Extract text
4. Convert text into a normalized internal format
5. Translate
6. Apply glossary / translation memory / cache
7. Run QA
8. Build or regenerate the game-localization files
9. Repack when necessary
10. Process Arabic rendering requirements
11. Validate in the real game
12. Support rollback if localization fails
```

Do not implement the entire architecture yet.

This task is intentionally limited.

---

# 4. Why Ren'Py Comes First

Phase 1 starts with **Ren'Py**.

The reason is not that Ren'Py is the final target.

The reason is that Ren'Py provides a manageable first engine for proving the entire architecture and establishing the adapter pattern.

The first major success criterion for the project is:

> A real Ren'Py game can go through the system successfully from extraction toward localization.

The current task is only the first half of that work.

---

# 5. Phase Structure

The original roadmap contains four major phases.

### Phase 1 — Foundation
- Core: pipeline + cache + SQLite
- First engine: Ren'Py, end-to-end
- Local translation: llama.cpp + Qwen 2.5
- Goal: successfully localize a real Ren'Py game

### Phase 2 — Arabic and Quality
- Arabic reshaping
- BiDi
- Fonts
- Word wrapping
- Character glossary
- Automated QA
- First RTL UI

### Phase 3 — Expansion
- Unity
- RPG Maker
- VNTextPatch integration
- Runtime injection
- Distribution and signing

### Phase 4 — Community
- TMX/XLIFF sharing
- Arabic documentation
- Contributors
- Arabic-focused LoRA / specialized model work

You are **NOT** implementing Phases 2–4 in this task.

---

# 6. What "First 50% of Phase 1" Means

Do not interpret "50%" as randomly writing half the files.

The first 50% should establish a functional, extensible foundation.

Implement these parts:

## A. Repository and Project Structure

Create a clean project structure suitable for long-term open-source development.

It should make a clear distinction between:

```text
core/
engine_adapters/
storage/
cli/
tests/
docs/
```

Use sensible names and keep responsibilities separated.

Do not create a monolithic project.

---

## B. Core Domain Model

Create the first version of the normalized localization representation.

At minimum, a localization entry should support concepts equivalent to:

```text
id
source_text
translated_text
speaker
context
engine
status
metadata
```

Design the model so it can later support:

- glossary matches
- translation memory
- QA flags
- translator/provider information
- checksums
- source references
- versioning

Do not overengineer it.

The goal is to create a stable internal contract that different engine adapters can use.

---

## C. SQLite Persistence

Create the first persistence layer using SQLite.

The system should be able to persist at least:

- localization entries
- source/original text
- translated text
- basic status
- metadata required for reconstruction

The database abstraction must be separated from business logic.

Do not scatter raw SQL throughout the application.

---

## D. Cache Foundation

Create the basic translation/cache abstraction.

The cache should allow the system to answer:

> "Have we already processed this exact source text under this relevant context?"

The design must be deterministic and reusable by later translation providers.

Do not build advanced AI optimization yet.

---

## E. Pipeline Abstraction

Create the initial pipeline interfaces and stages.

The architecture should make it possible to represent a flow similar to:

```text
Detect
→ Extract
→ Normalize
→ Translate
→ Validate
→ Export / Rebuild
```

For this task, only implement the stages that belong to the first half.

Make the interfaces explicit so that later adapters can plug into them.

Avoid hardcoding Ren'Py logic into the general pipeline core.

---

## F. Ren'Py Adapter — Extraction First

Build the first Ren'Py adapter with emphasis on extraction and normalization.

The adapter should be able to:

1. Accept a Ren'Py project/game path.
2. Locate relevant Ren'Py script resources.
3. Read supported script text.
4. Extract dialogue/text entries.
5. Preserve enough source information to later write the translation back.
6. Convert extracted text into the common internal localization model.
7. Export the normalized representation in a human-readable form for inspection/testing.

The extraction logic should be isolated from the rest of the core.

Do not make the entire system Ren'Py-specific.

---

## G. CLI Skeleton

Create a minimal command-line interface that demonstrates the current working path.

For example, commands conceptually like:

```text
detect
extract
inspect
db
```

Exact command names are up to you.

The important thing is that another developer can run a simple command and observe:

```text
game input
→ Ren'Py extraction
→ normalized entries
→ SQLite storage
```

---

## H. Tests and Fixtures

Create automated tests for the foundation.

At minimum include:

- core model tests
- SQLite persistence tests
- cache tests
- pipeline tests
- Ren'Py parsing/extraction tests
- fixture-based tests using a small sample Ren'Py project

Do not depend entirely on a huge real commercial game for testing.

Create a tiny deterministic test fixture.

---

# 7. Explicitly DO NOT Implement Yet

Stop after the first 50% foundation.

Do NOT spend the main implementation effort on:

- advanced AI translation
- full llama.cpp integration
- Qwen model downloading or management
- cloud providers
- advanced glossary logic
- character gender/narrative style system
- Arabic reshaping
- advanced BiDi handling
- automatic Arabic font injection
- advanced word wrapping
- runtime hooks
- BepInEx
- UE4SS
- Unity
- Unreal
- RPG Maker
- OCR
- adaptive runtime translation
- community sharing infrastructure
- LoRA training
- production-grade Tauri UI

These belong to later work or the second half of Phase 1.

If a tiny placeholder/interface is needed to keep architecture clean, that's fine.

Do not build the full feature.

---

# 8. Important Engineering Constraints

## Keep Dependencies Honest

Before adding a dependency, ask:

1. Do we really need it?
2. Is it open source?
3. What is its license?
4. Does its license fit the planned project?
5. Can the project remain maintainable if the dependency disappears?

Do not copy third-party source code just to move faster.

Prefer composition and adapters.

---

# 9. Licensing Philosophy

The intended project license is:

**AGPL-3.0**

This is deliberate because the project is intended to remain open and prevent proprietary closure of the main project.

However:

- verify third-party licenses
- keep attribution
- isolate third-party components appropriately
- do not assume every dependency can be included in every way
- maintain a `THIRD_PARTY_NOTICES` or equivalent record

Do not perform legal claims beyond what the actual license texts support.

---

# 10. Design Principles

Follow these rules while implementing:

### Principle 1 — Small Interfaces
Prefer small, composable interfaces.

### Principle 2 — Dependency Inversion
The Core should not directly depend on every engine.

### Principle 3 — Adapter Isolation
Each engine-specific implementation should remain replaceable.

### Principle 4 — Deterministic Data
The same input should produce predictable normalized output.

### Principle 5 — Reproducibility
A developer should be able to reproduce extraction from a fixture.

### Principle 6 — Fail Clearly
Errors should explain what happened and at which stage.

### Principle 7 — No Magic
Avoid hidden global state and undocumented behavior.

### Principle 8 — Future-Proof the Contract, Not the Entire System
Create good interfaces for future phases, but do not prematurely implement them.

---

# 11. Deliverables for This Task

When you finish, provide:

## 1. Implementation

The actual code for the first 50% of Phase 1.

## 2. Project Structure

Show the final project tree.

## 3. What Works

Clearly list what is already functional.

Example:

```text
✅ Project boots
✅ SQLite persistence works
✅ Core localization model works
✅ Cache works
✅ Pipeline abstraction works
✅ Ren'Py extraction works
✅ Extracted entries stored in SQLite
✅ CLI can execute extraction
✅ Tests pass
```

## 4. What Is Intentionally Not Done

Clearly list the remaining work in Phase 1.

Example:

```text
⏳ llama.cpp integration
⏳ Qwen 2.5 translation provider
⏳ translation execution
⏳ full Ren'Py reinjection
⏳ real-game end-to-end localization
```

## 5. Architecture Notes

Briefly explain:

- why the core is separated from the Ren'Py adapter
- how the normalized localization model works
- how SQLite is used
- how the cache is keyed
- how future engines can plug in
- where the translation provider will later connect

## 6. Run Instructions

Give exact commands needed to:

- install dependencies
- run the CLI
- run extraction on the test fixture
- inspect stored data
- run tests

## 7. Next Step

At the end, describe the **next 50% of Phase 1**, but do not implement it in this task.

---

# 12. Quality Bar

Do not optimize for the amount of code written.

Optimize for:

- clean architecture
- understandable code
- reliable extraction
- testability
- clear boundaries
- maintainability
- future extensibility

A smaller implementation that is structurally correct is better than a huge implementation full of shortcuts.

---

# 13. Working Style

Before coding:

1. Restate your understanding of the project in your own words.
2. State the exact scope you will implement.
3. Identify any assumptions you must make.
4. Then inspect the repository and existing files.
5. Then implement incrementally.
6. Run tests.
7. Fix failures.
8. Show the final state.

Do not silently expand the scope.

Do not jump ahead into Phase 2 or Phase 3.

Do not replace the architecture with a simpler unrelated toy implementation.

Build the **foundation of the actual intended project**.

---

# 14. Final Success Definition for This Task

This task is successful when another developer can clone the repository and run a small Ren'Py fixture through:

```text
Ren'Py fixture
      ↓
Ren'Py adapter
      ↓
Text extraction
      ↓
Normalized localization entries
      ↓
SQLite
      ↓
CLI inspection
      ↓
Tests pass
```

At that point, the project should have a real architectural foundation for the second half of Phase 1.

The ultimate vision remains:

> One open-source Arabic localization ecosystem that can grow from one engine to many engines, from offline local translation to optional cloud translation, and from static extracted text to runtime adaptive localization — while keeping the Arabic layer and the core infrastructure under our control.
