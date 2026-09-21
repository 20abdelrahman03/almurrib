# Almurrib — Phase 2, Second 50%
## Character Glossary + Real Font Metrics + First RTL UI + Localization Overlay Architecture

You are the lead implementation agent continuing **Almurrib (المعرب)** after the successful completion of the **first 50% of Phase 2**.

The original roadmap defines Phase 2 as:
- Arabic reshaping / BiDi / fonts / word wrapping
- Character glossary with gender and language/style level
- Automatic Arabic QA
- First RTL UI

The first 50% has already implemented:
- Unicode normalization
- Arabic reshaping
- BiDi processing
- Arabic-aware wrapping foundation
- font/resource foundation
- structured Arabic QA
- placeholder/markup protection
- integration into the production translation pipeline
- Ren'Py export
- adversarial testing
- real Ren'Py visual-test assembly

The remaining task is the **SECOND 50% OF PHASE 2**.

---

# 1. Mission

Complete the second half of Phase 2 without starting Phase 3.

Main goals:
1. Character / terminology glossary
2. Gender-aware and style-aware translation context
3. Glossary-aware QA
4. Real font metrics where practical
5. Better Arabic wrapping using metrics
6. First RTL UI foundation
7. Explicit localization-overlay architecture
8. Ren'Py regression / E2E validation
9. Deep adversarial testing and self-audit
10. Preserve all existing Phase 1 + Phase 2 first-50% behavior

---

# 2. HARD PRODUCT REQUIREMENT — LOCALIZATION OVERLAY

This is a **hard requirement** for Almurrib.

## The game's original/base language should remain English whenever possible.

Do NOT design Almurrib around the assumption that every target game must expose:

```text
Arabic
العربية
ar
```

as a new selectable language.

Many games hard-code their language menus or do not support registering a new locale cleanly.

Therefore:

> **Almurrib should prefer making Arabic appear as an overlay/replacement while leaving the game's original/base locale as English, whenever the target engine permits it.**

Conceptually:

```text
Game base locale = English
        ↓
Almurrib localization overlay
        ↓
Arabic localized content
        ↓
Player sees Arabic
```

The player's game settings may still say:

```text
Language = English
```

while Almurrib causes the visible game text to be Arabic.

### Critical distinction

The temporary `ar` locale used in the current Ren'Py visual test is a **test mechanism for rendering**, not the universal product architecture.

Do not assume every engine can or should add Arabic to its official language list.

---

# 3. ENGINE-ADAPTER IMPLICATION

Do NOT implement Phase 3 runtime injection now.

Do, however, create clean abstractions that future adapters can use for strategies such as:

- localized-string replacement
- lookup override
- resource patching
- runtime text interception
- engine-specific overlay

The common architecture must be able to represent:

```text
Base locale: English
Displayed localization: Arabic
Overlay active: yes
```

The exact mechanism remains engine-specific.

---

# 4. RECONNAISSANCE FIRST

Before coding, inspect the whole current repository:

```text
src/almurrib/
tests/
fixtures/
docs/
pyproject.toml
README.md
THIRD_PARTY_NOTICES.md
```

Especially:

```text
core/model.py
core/pipeline.py
core/translate.py
core/workflow.py
core/placeholders.py
core/provider.py
core/config.py
core/reporting.py
arabic/
storage/
engine_adapters/renpy/
providers/
gui/
```

Understand and reuse:
- LocalizationEntry
- EntryStatus
- QA flags
- provenance
- translation memory
- cache
- provider selection
- Ren'Py extraction/export
- Arabic processing
- font resources
- GUI/CLI workflow

Do NOT create a parallel glossary, QA, storage, or translation architecture.

---

# 5. PRESERVE THE FIRST 50%

Do not regress:

- canonical vs render-ready separation
- placeholder safety
- markup safety
- Unicode normalization
- reshaping
- BiDi
- word wrapping
- Arabic QA
- cache/TM provenance
- Ren'Py export
- CLI
- GUI
- EXE packaging
- fixture safety

Run the full existing suite before and after the work.

---

# 6. CHARACTER / TERMINOLOGY GLOSSARY

Implement a structured glossary.

At minimum support concepts equivalent to:

```text
GlossaryEntry
    source_term
    target_term
    type
    notes
    gender
    style
    pronunciation
    aliases
    enabled
    metadata
```

Exact fields are your decision.

Support:

### Characters

```text
Sylvie → سيلفي
gender = female
style = colloquial
```

### Terms

```text
visual novel → رواية بصرية
```

### Aliases / variants

Support source aliases where practical without unsafe over-normalization.

---

# 7. GENDER + STYLE CONTEXT

Create a provider-independent representation such as:

```text
TranslationContext
    speaker
    speaker_gender
    speaker_style
    glossary_matches
    nearby_context
```

The translation layer should be able to pass this context to providers.

Do NOT hard-code grammar behavior into provider-specific implementations.

The context is guidance, not a guarantee of perfect Arabic.

Suggested style/register values may include:

```text
formal
standard
colloquial
rough
polite
childlike
technical
```

Exact enum is your decision.

---

# 8. GLOSSARY-AWARE TRANSLATION

Integrate glossary lookup into the existing translation flow.

Desired concept:

```text
source
  ↓
glossary matching
  ↓
translation context
  ↓
provider
  ↓
placeholder validation
  ↓
Arabic QA
  ↓
canonical Arabic
```

Reuse any existing normalization/dictionary stage instead of creating another pipeline.

Distinguish:

```text
glossary-enforced
glossary-suggested
no match
```

Do not blindly perform arbitrary post-translation substring replacement when it could damage grammar or markup.

---

# 9. GLOSSARY-AWARE QA

Extend the existing structured QA engine.

Examples:

```text
expected: سيلفي
actual:   سيلفيه
```

Potential result:

```text
rule_id = glossary.mismatch
severity = warning/error
evidence = ...
expected = ...
actual = ...
```

Check:
- missing expected terms
- inconsistent character names
- forbidden variants
- conflicting glossary entries

Be careful with grammatical inflection; do not flag valid forms just because they are not byte-identical to the glossary target.

---

# 10. GLOSSARY STORAGE

Integrate glossary data into the existing persistence architecture.

Do NOT create a second unrelated database.

Support:
- project scope
- game/engine scope where needed
- deterministic tests
- future import/export
- future TMX/XLIFF compatibility

Add migrations if required and preserve backward compatibility.

---

# 11. GLOSSARY IMPORT / EXPORT FOUNDATION

Do not build Phase 4 community sharing.

Provide a simple human-editable representation, for example:

```text
JSON
CSV/TSV
```

Document the format.

No GitHub synchronization or community sharing in this task.

---

# 12. REAL FONT METRICS

The first 50% used deterministic fallback metrics.

Now implement a practical measurement abstraction where feasible:

```python
FontMetrics:
    measure(text, font, size)
    line_height(...)
    glyph_width(...)
```

Exact API is your decision.

Evaluate existing libraries before adding dependencies, such as:
- fontTools
- FreeType
- HarfBuzz

Check:
- license
- Windows compatibility
- PyInstaller packaging
- performance
- actual necessity

Do not add a heavy dependency simply because it exists.

---

# 13. METRIC-AWARE ARABIC WRAPPING

Upgrade the current wrapping layer to use real metrics when available.

Handle:
- Arabic word boundaries
- whitespace
- punctuation
- Arabic + Latin
- numbers
- placeholders
- markup
- URLs
- explicit newlines
- long unbreakable tokens

Conceptually:

```text
logical Arabic
    ↓
protect placeholders/markup
    ↓
tokenize
    ↓
measure
    ↓
wrap
    ↓
restore protected content
```

Never replace canonical stored text with wrapped/render-ready output.

---

# 14. FONT RESOURCE SYSTEM

Complete the font foundation enough for real project use.

Support metadata such as:

```text
FontAsset
    name
    path
    format
    license
    family
    weight
    style
    source
```

Candidate fonts from the project plan:
- Vazirmatn
- Lalezar
- Noto Naskh
- Cairo
- Amiri

Do not bundle every font blindly.

Choose a sensible default and document why.

Prefer project-local fonts. Do not globally install fonts into Windows.

Preserve license notices.

---

# 15. FIRST RTL UI

Implement the first real RTL-capable Almurrib UI foundation.

This is NOT the final polished UI.

Prove:
- RTL layout direction
- Arabic labels
- Arabic text entry
- mixed Arabic/English
- proper control alignment
- readable status messages
- right-to-left flow
- LTR still possible

Reuse the current GUI architecture. Do not replace it wholesale.

Prefer switchable layout direction:

```text
LTR
RTL
```

rather than hard-coding every widget for Arabic.

---

# 16. GUI LOCALIZATION ARCHITECTURE

Separate UI strings from widget logic:

```text
UI strings
    ↓
localization resource
    ↓
current UI locale
```

Start with Arabic + English.

Do not hard-code every visible string deep inside widget logic.

---

# 17. DO NOT CONFUSE THESE THREE LANGUAGES/CONCEPTS

They are separate:

```text
Almurrib UI language
        ≠
Target game's base/original locale
        ≠
Displayed game localization
```

Example:

```text
Almurrib UI = Arabic
Game base locale = English
Displayed game text = Arabic via Almurrib overlay
```

The architecture must support this.

---

# 18. REN'PY E2E REGRESSION

Keep using `the_question`.

Verify:
- glossary persistence
- glossary context reaches translation workflow
- glossary QA works
- exported output reparses
- original files remain untouched
- canonical text remains logical
- render-ready text remains derived
- repeated runs stay stable

The temporary `ar` button used by the manual rendering test must be documented as a test-only mechanism, not the final product architecture.

---

# 19. ADVERSARIAL TESTING

Attack the new systems.

### Glossary
- duplicate entries
- conflicts
- overlapping terms
- case variants
- aliases
- missing metadata
- disabled entries
- malformed imports

### Translation context
- missing speaker
- unknown gender
- unknown style
- conflicting context
- provider unavailable
- provider ignoring context

### Metrics
- missing font
- invalid font
- missing glyph
- huge font size
- zero/negative width
- long URLs
- long identifiers
- Arabic + English
- placeholders
- markup

### UI
- long Arabic labels
- Arabic input
- mixed RTL/LTR
- English fallback
- empty strings
- long errors
- dialogs
- resizing

---

# 20. INVARIANTS

Preserve:

```text
canonical_translation is never replaced by render-ready text
placeholder_set(before) == placeholder_set(after)
```

where applicable.

Glossary determinism:

```text
same input + same glossary version = same result
```

Pipeline stability:

```text
run(run(project)) == stable project state
```

where the current architecture promises it.

---

# 21. SELF-AUDIT

After all tests pass, perform a second independent review.

Look for:
- duplicate architectures
- broad exception handling
- silent fallbacks
- mutable global state
- encoding/path assumptions
- Windows/PyInstaller bugs
- migration problems
- project-scope contamination
- cache/TM contamination
- provider-context leakage
- double-processing
- incorrect RTL assumptions
- font-resource mistakes
- false-positive/false-negative glossary QA

For every real bug:

```text
reproduce
→ regression test
→ fix
→ targeted tests
→ full suite
```

Do not hide discovered problems.

---

# 22. PERFORMANCE

Measure at minimum:

```text
100 glossary lookups
1,000 glossary lookups
10,000 glossary lookups

short/medium/long wrapping
repeated font measurement
```

Compare with baseline where practical.

Do not optimize before measuring.

---

# 23. BACKWARD COMPATIBILITY

Verify all current commands still work:

```text
almurrib --help
almurrib detect
almurrib extract
almurrib inspect
almurrib db
almurrib translate
almurrib export
almurrib localize
almurrib-gui
```

Also:
- providers
- cache
- TM
- provenance
- Ren'Py adapter
- export
- Arabic processing
- QA
- EXE

---

# 24. PACKAGING

Verify:

```powershell
.\.venv\Scripts\python build_exe.py
```

and, where practical:

```text
dist\Almurrib.exe
```

Check:
- glossary resources
- font resources
- UI localization resources
- new dependencies
- resource paths
- database paths
- PyInstaller imports

---

# 25. DOCUMENTATION

Update/create:

```text
docs/GLOSSARY.md
docs/FONT_METRICS.md
docs/RTL_UI.md
docs/PHASE2_STATUS.md
```

Document:
- glossary model
- gender/style semantics
- glossary QA
- font metrics
- wrapping behavior
- resource packaging
- RTL UI architecture
- localization-overlay principle
- Ren'Py test behavior
- limitations
- future adapter implications

Explicitly document:

> The game's base/original language should remain unchanged where possible; Almurrib should overlay/replace displayed content with Arabic rather than requiring every game to register Arabic as an official locale.

---

# 26. PHASE 3 FIREWALL

DO NOT implement:
- Unity adapter
- UnityPy
- UABEA
- AssetsTools.NET
- Cpp2IL
- BepInEx runtime injection
- XUnity.AutoTranslator
- Unreal adapter
- repak
- UAssetAPI
- UE4SS
- RPG Maker adapter
- full VNTextPatch integration
- runtime injection framework
- Velopack distribution work
- SignPath setup
- community TMX/XLIFF sharing
- LoRA/model training

You may prepare clean interfaces for future Phase 3 adapters.

Do not implement Phase 3 functionality.

---

# 27. DEFINITION OF DONE

## Glossary
- [ ] structured glossary exists
- [ ] character metadata
- [ ] gender
- [ ] style/register
- [ ] aliases
- [ ] deterministic lookup
- [ ] translation context integration
- [ ] glossary-aware QA
- [ ] existing persistence integration
- [ ] minimal import/export foundation

## Font Metrics
- [ ] real measurement abstraction
- [ ] real font measurement where available
- [ ] deterministic fallback
- [ ] metric-aware Arabic wrapping
- [ ] packaging verified

## RTL UI
- [ ] RTL-capable Almurrib UI
- [ ] Arabic labels
- [ ] Arabic text input
- [ ] mixed Arabic/English
- [ ] LTR remains possible
- [ ] UI strings separated from widget logic

## Localization Overlay
- [ ] game locale distinguished from displayed localization
- [ ] English can remain the game's base locale
- [ ] Arabic overlay/replacement represented in common architecture
- [ ] Ren'Py test locale documented as temporary test mechanism

## E2E
- [ ] Ren'Py pipeline still works
- [ ] glossary survives persistence
- [ ] export reparses
- [ ] originals remain untouched
- [ ] repeated runs stable

## Regression
- [ ] all previous tests pass
- [ ] new tests pass
- [ ] GUI starts
- [ ] EXE builds

---

# 28. FINAL REPORT — EXACT STRUCTURE

## 1. Executive Summary
## 2. Architecture Changes
## 3. Exact Files Changed
## 4. Glossary
## 5. Font Metrics
## 6. RTL UI
## 7. Localization Overlay
Explain:
- game base locale
- displayed localization
- Almurrib UI locale

## 8. Ren'Py E2E
## 9. Adversarial Testing
## 10. Bugs Found
For each:
- reproduction
- root cause
- fix
- regression test

## 11. Bugs Not Fixed
## 12. Test Results
Exact commands and counts.

## 13. Performance
Actual measurements.

## 14. Packaging
CLI / GUI / EXE.

## 15. Documentation
## 16. Remaining Risks
Use:
```text
CRITICAL
HIGH
MEDIUM
LOW
```

## 17. Phase 3 Readiness
Describe what interfaces are ready for future engine adapters.

Do NOT implement Phase 3.

---

# 29. FINAL SELF-AUDIT QUESTION

Before finishing, answer:

> If the game says "English" as its base language, can Almurrib conceptually make the player see Arabic without requiring the game itself to officially add Arabic to its language list?

The architecture should support this principle without pretending every engine implements it identically.

---

# ABSOLUTE RULES

1. Do NOT start Phase 3.
2. Do NOT rewrite the Phase 1 provider architecture.
3. Do NOT replace the current Arabic layer.
4. Do NOT break canonical text storage.
5. Do NOT store irreversible render-ready Arabic as canonical text.
6. Do NOT require a new Arabic game locale as a universal assumption.
7. Do NOT treat the temporary Ren'Py `ar` test button as final product architecture.
8. Do NOT add unrelated heavy dependencies.
9. Do NOT silently swallow errors.
10. Do NOT hide discovered bugs.
11. Do NOT modify original game fixtures destructively.
12. Do NOT expose secrets.
13. Do NOT commit unless explicitly requested.
14. Do not claim visual behavior is verified unless actually observed or instrumented.
15. Keep the project understandable to a future maintainer.

# SUCCESS CONDITION

At the end:

```text
                         ALMURRIB
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
         Arabic Layer                Glossary
       normalize/reshape             names
       BiDi/wrap/fonts               gender
              │                       style
              └──────────┬──────────────┘
                         ▼
                    Translation
                         │
                         ▼
                    Arabic QA
                         │
                         ▼
                Canonical Arabic
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        Font Metrics             RTL UI
              │
              ▼
     Future Localization Overlay
              │
     Game base locale can remain English
              │
              ▼
       Arabic displayed to player
```

The project should be ready for **Phase 3 engine expansion** after this task, but Phase 3 itself must remain untouched.
