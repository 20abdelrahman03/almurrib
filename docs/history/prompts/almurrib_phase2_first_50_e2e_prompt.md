# Almurrib — Phase 2, First 50%
## Arabic Layer + Arabic QA — Deep E2E Implementation, Adversarial Testing, and Self-Audit

You are continuing work on **Almurrib (المعرب)** after Phase 1 was implemented, refactored, stabilized, and tested across multiple AI providers.

Phase 1 currently has this real pipeline:

```text
Ren'Py game
→ detect
→ extract
→ normalize
→ SQLite
→ translation provider
→ cache / TM / provenance
→ placeholder validation
→ Ren'Py localization export
```

The original project plan defines Phase 2 as:

- Arabic layer: reshaping + BiDi + fonts + word wrapping
- Character glossary with gender and language/style level
- Automatic Arabic QA
- First RTL interface

This task is the **FIRST 50% of Phase 2**.

Focus on:

1. Arabic processing abstraction
2. Unicode normalization
3. Arabic reshaping
4. BiDi processing
5. Arabic-aware word wrapping
6. Font/resource foundation
7. Arabic QA engine
8. Integration into the real Phase 1 pipeline
9. Ren'Py E2E verification
10. Adversarial testing and self-audit

Defer primarily to the second 50%:

- full character glossary/editor
- full Tauri + React RTL UI
- other game engines
- runtime injection
- Phase 3 features
- community TMX/XLIFF
- LoRA/model training

Do NOT redesign Phase 1 unnecessarily.

---

# 1. MANDATORY RECONNAISSANCE

Before coding, inspect the entire current repository:

```text
src/almurrib/
tests/
fixtures/
docs/
pyproject.toml
README.md
THIRD_PARTY_NOTICES.md
```

Especially inspect:

```text
core/model.py
core/pipeline.py
core/translate.py
core/workflow.py
core/placeholders.py
core/provider.py
core/config.py
core/reporting.py
storage/
engine_adapters/renpy/
providers/
gui/
```

Understand the current:

- LocalizationEntry
- EntryStatus
- QA flags
- provenance
- cache
- translation memory
- provider system
- Ren'Py extraction/export
- GUI/CLI workflow

Do not create a second disconnected localization/QA architecture.

---

# 2. IMPORTANT ENGINEERING RULE

Do NOT treat this as:

> "Implement the checklist and make tests pass."

Treat it as:

> "Implement the Arabic layer, then actively try to break it."

You MUST investigate likely bugs yourself.

Green tests are NOT sufficient evidence.

Think like:

- Unicode engineer
- localization engineer
- game text rendering engineer
- QA engineer
- hostile tester
- maintainer inheriting the project

At the end distinguish:

```text
Implemented
Verified offline
Verified E2E
Experimentally verified
Unverified
Known limitations
Bugs found
Bugs fixed
Bugs deferred
```

---

# 3. ARABIC PROCESSING ARCHITECTURE

Create a clean engine-independent Arabic processing abstraction.

Possible conceptual API:

```python
ArabicTextProcessor:
    normalize()
    reshape()
    apply_bidi()
    wrap()
    validate()
```

Exact API is your decision.

Requirements:

- deterministic
- testable
- reusable by future Unity/Unreal/RPG Maker adapters
- independent of GUI
- independent of translation provider
- canonical translation must remain recoverable

IMPORTANT:

Do NOT permanently replace the canonical stored translation with irreversible reshaping/BiDi output.

Prefer:

```text
canonical translation
        ↓
Arabic processing
        ↓
render-ready representation
```

---

# 4. DEPENDENCIES

Investigate before installing:

- `arabic-reshaper`
- `python-bidi`
- HarfBuzz bindings if genuinely needed

Also inspect licensing and packaging impact.

Do not blindly install every library mentioned in the project plan.

Check:

- license compatibility
- Python compatibility
- Windows packaging
- PyInstaller behavior
- maintenance
- actual necessity

Update:

```text
pyproject.toml
THIRD_PARTY_NOTICES.md
```

for every new runtime dependency.

---

# 5. UNICODE NORMALIZATION

Implement deterministic normalization.

Investigate:

- Unicode NFC/NFD
- Arabic letter variants
- Arabic-Indic vs Latin digits
- Arabic punctuation
- Tatweel
- diacritics
- zero-width characters
- directional marks
- whitespace
- newlines

Do NOT aggressively delete meaningful content.

Do not blindly remove:

```text
ً ٌ ٍ َ ُ ِ ّ ْ ٰ
```

Protect existing game syntax:

```text
{name}
{player_name}
{0}
%s
%d
%1$s
[variable]
<color=red>
</color>
<b>


	
```

Normalization must not corrupt them.

---

# 6. ARABIC RESHAPING

Implement reshaping through a clean API.

Test at minimum:

```text
السلام عليكم
المعرب
محمد
مدرسة
لغة عربية
```

and:

```text
Hello مرحبًا
مرحبا 123
{name} مرحبًا
<color=red>مرحبا</color>
```

IMPORTANT:

Do not assume every renderer needs reshaping.

Distinguish:

```text
logical Arabic text
```

from:

```text
render-ready shaped text
```

If shaping is renderer-specific, make that explicit.

Test repeated processing:

```text
process(process(text))
```

and determine whether it is idempotent.

If not, document and guard against accidental double processing.

---

# 7. BiDi

Implement a reusable BiDi layer.

Test:

```text
مرحبا بالعالم
مرحبا OpenAI
السعر 123 جنيه
استخدم Qwen3 للترجمة
اضغط Enter للمتابعة
HP: 100
مرحبا {player_name}
<color=red>مرحبا</color>
```

Also test:

- punctuation
- parentheses
- quotes
- numbers
- URLs
- file names
- model names
- placeholders
- markup
- newline-separated strings
- mixed Arabic/Latin
- Arabic + Japanese
- Arabic + Chinese
- Arabic + Russian
- emoji

Do not declare every mixed-direction string broken. Some are correct.

---

# 8. PLACEHOLDER / MARKUP SAFETY

This is critical.

Arabic processing must preserve:

```text
{name}
{0}
%s
%d
%1$s
[variable]
<color=red>
</color>
<b>


	
```

Use the existing placeholder system rather than duplicating it.

Verify invariants such as:

```text
placeholder_set(before) == placeholder_set(after)
```

where appropriate.

Test markup separately.

---

# 9. WORD WRAPPING

Build the first real Almurrib Arabic word-wrapping layer.

Do not assume `textwrap.wrap()` is sufficient.

Investigate:

- Arabic word boundaries
- whitespace
- punctuation
- Arabic + Latin
- numbers
- placeholders
- markup
- explicit newlines
- very long words
- ZWJ/ZWNJ
- URLs

Create a reusable API similar to:

```python
wrap_arabic_text(
    text,
    max_width,
    metrics=None,
    preserve_markup=True,
)
```

Do not assume character count equals rendered width.

If actual font metrics are unavailable, create a clear metrics abstraction and deterministic fallback. Document the limitation.

Test invalid widths and impossible wrapping parameters.

---

# 10. FONT / RESOURCE FOUNDATION

Do not build every engine-specific font injector yet.

Create a foundation capable of representing:

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

Investigate the project-plan fonts:

- Vazirmatn
- Lalezar
- Noto Naskh
- Cairo
- Amiri

Respect licenses and attribution.

At this stage prioritize:

- discovery
- metadata
- resource packaging strategy
- future adapter compatibility

over engine-specific injection.

---

# 11. ARABIC QA ENGINE

Create a structured QA engine integrated with existing Almurrib QA/provenance concepts.

The project plan identifies:

1. leftover English
2. bad transliteration
3. punctuation
4. mixed BiDi
5. excessive length
6. glossary mismatch
7. untranslated lines

For this first 50%, implement rules that do not require the full future character glossary, while leaving a clean extension point for glossary-aware rules.

Do NOT make QA merely a list of free-form strings.

Use a structured result, e.g.:

```python
QAResult(
    passed=True,
    severity="warning",
    flags=[
        QAFlag(
            rule_id="...",
            severity="...",
            message="...",
            evidence="..."
        )
    ]
)
```

Exact model is up to you.

---

# 12. QA RULES

## A. Source copied unchanged

Detect:

```text
source_text == translated_text
```

when source and target differ.

Handle legitimate identifiers carefully.

---

## B. Missing Arabic / suspicious Latin

Detect suspicious untranslated Latin.

Do NOT flag every Latin token.

These may be legitimate:

```text
OpenAI
Qwen3
HP
FPS
DLC
Ren'Py
```

Use heuristics and explainable reason codes.

---

## C. Arabic presence

For English → Arabic, flag translations containing no Arabic script when Arabic is reasonably expected.

Avoid treating every proper noun as an error.

---

## D. Punctuation

Detect suspicious English punctuation in Arabic:

```text
,
.
?
!
:
;
```

versus:

```text
،
؛
؟
```

QA should normally flag rather than silently mutate.

---

## E. Placeholders

Reuse/extend existing placeholder validation.

Detect:

- missing
- altered
- malformed
- duplicated when relevant
- markup corruption

---

## F. Length

The project plan mentions approximately `1.3×`.

Implement a configurable heuristic.

Do not assume character count equals visual width.

Use warning/error severity appropriately.

---

## G. Mixed direction

Detect potentially suspicious BiDi structures.

Do not declare all Arabic+Latin text invalid.

---

## H. Extensibility

Create a hook for future:

```text
character glossary
name consistency
gender consistency
formality/style
```

but do not build the full glossary system now.

---

# 13. PIPELINE INTEGRATION

The intended flow becomes:

```text
Translation
    ↓
Placeholder QA
    ↓
Arabic QA
    ↓
Arabic processing
    ↓
Persistence
    ↓
Export
```

Keep canonical translation separate from render-ready processing.

Do not make a renderer-specific transformation permanently overwrite the database's canonical translation.

Review how QA interacts with:

```text
TRANSLATED
FLAGGED
REVIEWED
APPROVED
OBSOLETE
```

Make the smallest backward-compatible change possible.

---

# 14. REN'PY E2E — MANDATORY

Do NOT stop at unit tests.

Use:

```text
fixtures/the_question
```

and/or create a dedicated Arabic fixture.

Exercise the real production path:

```text
extract
→ translate with FakeProvider/deterministic provider
→ Arabic QA
→ Arabic processing
→ SQLite
→ Ren'Py export
→ reparse
```

Verify:

- expected entry count survives
- Arabic survives persistence
- placeholders survive
- markup survives
- newline escapes survive
- QA flags persist
- generated localization remains parseable
- original game files remain byte-for-byte untouched

This must use production code, not a parallel demo implementation.

---

# 15. PURPOSE-BUILT ARABIC FIXTURE

Create a deterministic fixture containing:

```text
مرحبا بالعالم
Hello مرحبًا
لديك 125 نقطة
مرحبا {player_name}
<color=red>خطر!</color>
السطر الأول
السطر الثاني
استخدم Qwen3 للترجمة
هل تريد المتابعة؟
This sentence was not translated.
```

Also include:

- long Arabic sentence
- long unbroken token
- mixed UI text such as `HP: 100`
- punctuation
- quotes
- parentheses
- escaped syntax

Document the fixture.

---

# 16. ADVERSARIAL TESTING — REQUIRED

After the normal tests pass, deliberately try to break the implementation.

Test:

## Unicode

- NFC/NFD
- combining marks
- diacritics
- Tatweel
- ZWJ
- ZWNJ
- RTL/LTR marks
- mixed scripts
- emoji

## Punctuation

- Arabic punctuation
- English punctuation
- parentheses
- brackets
- quotes

## Numbers

- Latin digits
- Arabic-Indic digits
- percentages
- decimals
- dates
- version numbers

## Game syntax

- placeholders
- format strings
- markup
- escaped quotes
- `\n`
- `\t`

## Long text

- 500+ chars
- huge word with no spaces
- huge punctuation sequences

## Mixed languages

- Arabic + English
- Arabic + Japanese
- Arabic + Chinese
- Arabic + Russian
- URLs
- email addresses
- model IDs

## Empty/edge input

- empty
- whitespace-only
- newline-only
- invalid width
- negative width

## Reprocessing

Run Arabic processing twice and investigate whether:

```text
process(process(text))
```

is safe.

---

# 17. PROPERTY / FUZZ-LIKE TESTING

Where practical, create deterministic standard-library generators combining:

```text
Arabic
Latin
digits
punctuation
placeholders
markup
newlines
```

Assert invariants such as:

```text
placeholder_set(before) == placeholder_set(after)
```

and:

```text
valid_unicode_does_not_crash_processing
```

and:

```text
exported_output_is_reparseable
```

Do not add a large property-testing dependency unless clearly justified.

---

# 18. FAILURE INJECTION

Deliberately feed:

- malformed Unicode
- empty strings
- malformed markup
- missing placeholders
- unknown tags
- very long strings
- invalid widths
- corrupted translation data

Observe whether failures are:

```text
clear
recoverable
correctly classified
secret-safe
non-destructive
```

Fix genuine bugs discovered.

Every real bug found should get a regression test.

---

# 19. PERFORMANCE

Measure the Arabic layer on approximately:

```text
75 entries
1,000 entries
10,000 entries
```

Measure where practical:

```text
normalization
reshaping
BiDi
QA
wrapping
memory
```

Use actual measurements.

Do not invent performance claims.

---

# 20. MANUAL / STATIC BUG HUNT

After all tests pass, independently review your own implementation.

Search for:

```text
TODO
FIXME
pass
except Exception
return None
silent fallback
hard-coded Arabic assumptions
string replacement
regex-only Unicode handling
global mutable state
double processing
lossy normalization
encoding assumptions
path assumptions
```

Inspect:

- database persistence
- GUI
- CLI
- EXE
- package imports
- resource paths
- font paths
- Windows paths
- UTF-8 handling

Ask:

> What happens on a real game instead of the fixture?

Do not stop at what the tests happen to cover.

---

# 21. REAL ENGINE / VISUAL EXPERIMENT

If a real Ren'Py runtime is available:

Create/run a tiny test game containing:

```text
مرحبا بالعالم
Hello مرحبا
مرحبا {name}
markup
numbers
punctuation
```

Inspect actual rendering.

If Ren'Py runtime is unavailable:

DO NOT fake this.

Report:

```text
UNVERIFIED — real engine rendering unavailable
```

and explain exactly what remains to be tested.

---

# 22. WINDOWS / EXE

Verify:

```powershell
.\.venv\Scripts\python build_exe.py
```

and, if practical:

```text
dist\Almurrib.exe
```

Check:

- Arabic dependencies
- font resources
- package imports
- resource paths
- config paths
- database paths
- generated output

Do not assume source-tree-relative resources work inside PyInstaller.

---

# 23. BACKWARD COMPATIBILITY

All existing Phase 1 functionality must continue to work:

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

Existing:

- provider architecture
- cache
- TM
- provenance
- Ren'Py adapter
- export
- EXE

must remain functional.

Run the complete existing suite.

---

# 24. TEST QUALITY

Do NOT optimize for a huge test count.

A meaningful suite is:

```text
real failure modes
+
invariants
+
E2E
+
adversarial tests
+
regressions
```

A green test suite does not prove correctness if it never exercises the dangerous paths.

---

# 25. DOCUMENTATION

Update/create:

```text
docs/ARABIC_LAYER.md
docs/QA.md
docs/PHASE2_STATUS.md
```

Document:

- architecture
- canonical vs render-ready text
- normalization
- reshaping
- BiDi
- word wrapping
- fonts/resources
- QA rules
- severity
- dependencies
- licenses
- E2E workflow
- known limitations
- testing commands

Do not claim real engine rendering unless actually verified.

---

# 26. GIT SAFETY

Before changes:

```powershell
git status
git diff
```

Preserve existing user work.

Do not reset/revert unrelated work.

At the end:

```powershell
git diff --stat
git status
```

Do not commit unless explicitly requested.

---

# 27. DEFINITION OF DONE

The task is complete only when:

### Arabic layer

- [ ] abstraction exists
- [ ] normalization exists
- [ ] reshaping exists
- [ ] BiDi exists
- [ ] Arabic-aware wrapping foundation exists
- [ ] font/resource foundation exists

### QA

- [ ] structured QA engine exists
- [ ] source-copy detection
- [ ] suspicious English/Latin detection
- [ ] Arabic presence detection
- [ ] punctuation checks
- [ ] placeholder integration
- [ ] length checks
- [ ] mixed-direction checks
- [ ] future glossary extension point

### E2E

- [ ] real Almurrib entries pass through Arabic QA
- [ ] Arabic processing uses production code
- [ ] SQLite persistence works
- [ ] Ren'Py export works
- [ ] generated output reparses
- [ ] original files remain untouched

### Adversarial

- [ ] Unicode edge cases
- [ ] mixed scripts
- [ ] placeholders
- [ ] markup
- [ ] long strings
- [ ] double-processing
- [ ] failure injection
- [ ] manual/static bug hunt

### Regression

- [ ] all Phase 1 tests pass
- [ ] CLI works
- [ ] GUI starts
- [ ] EXE builds

### Documentation

- [ ] Arabic layer documented
- [ ] QA documented
- [ ] Phase 2 status documented
- [ ] dependency/license docs updated

---

# 28. FINAL SELF-AUDIT

After implementation and after all tests pass:

STOP coding temporarily.

Perform a second independent review as if you were reviewing someone else's PR.

Look specifically for:

- incorrect Unicode assumptions
- lossy transformations
- double-processing
- placeholder corruption
- markup corruption
- incorrect BiDi behavior
- punctuation mistakes
- QA false positives
- QA false negatives
- Windows/path bugs
- EXE resource bugs
- database compatibility issues
- cache/TM contamination
- performance regressions
- error swallowing
- silent fallbacks
- documentation drift
- test gaps

For every real bug:

1. reproduce it
2. add regression test
3. fix it
4. rerun targeted tests
5. rerun full suite

Do not hide discovered problems to make the report look clean.

---

# 29. FINAL REPORT — EXACT STRUCTURE

At the end write a detailed final report with:

## 1. Executive Summary
What changed and what was actually verified.

## 2. Architecture Changes
Before/after.

## 3. Exact Files Changed
Added / modified / deleted.

## 4. Dependencies
Name, version, purpose, license, packaging impact.

## 5. Arabic Processing
Normalization, reshaping, BiDi, wrapping, fonts/resources.

## 6. QA Engine
Every rule, detection logic, severity, false-positive/negative considerations.

## 7. E2E Verification
Exact execution trace and results:

```text
Ren'Py
→ extract
→ translate
→ Arabic QA
→ Arabic processing
→ SQLite
→ export
→ reparse
```

## 8. Adversarial Testing
Everything deliberately attacked and the result.

## 9. Bugs Found During Self-Audit
For each: reproduction, root cause, fix, regression test.

## 10. Bugs Not Fixed
Do not hide them. Explain why.

## 11. Test Results
Exact commands and exact passed/failed/skipped counts.

## 12. Performance
Actual measurements.

## 13. Real Engine Verification
Clearly label:

```text
VERIFIED
UNVERIFIED
NOT AVAILABLE
```

## 14. Backward Compatibility
Phase 1 regression status.

## 15. Documentation
Files updated.

## 16. Final Risk Assessment

Categorize:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

No vague "everything is fine".

## 17. Recommended Next Step
Explain what the second 50% of Phase 2 should implement, but DO NOT implement it now.

---

# ABSOLUTE RULES

1. Do NOT move to Phase 3.
2. Do NOT build the full Tauri/React UI.
3. Do NOT add other game engines.
4. Do NOT replace the provider architecture.
5. Do NOT break Phase 1.
6. Do NOT modify original game fixtures destructively.
7. Do NOT silently swallow errors.
8. Do NOT claim tests prove things they do not prove.
9. Do NOT claim real rendering without a real engine run.
10. Do NOT stop at unit tests.
11. Actively search for bugs.
12. Fix genuine bugs and add regressions.
13. Keep canonical translations lossless.
14. Protect placeholders and markup.
15. Preserve secrets.
16. Do not commit unless explicitly requested.
17. Be honest about unverified behavior.

# FINAL SUCCESS CONDITION

The desired result is:

```text
                    ALMURRIB
                       │
                       ▼
                Translation Entry
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
        Canonical Text       Metadata
             │
             ▼
      Arabic QA Engine
             │
       ┌─────┴─────┐
       ▼           ▼
     PASS        FLAGS
       │           │
       └─────┬─────┘
             ▼
      Arabic Processing
       │      │      │
       ▼      ▼      ▼
    Reshape  BiDi   Wrap
             │
             ▼
       Render-ready
             │
             ▼
       Ren'Py Export
             │
             ▼
          Reparse
             │
             ▼
       Verified Output
```

The success criterion is NOT:

> "We installed Arabic libraries."

It is:

> **Almurrib now has a tested, reusable Arabic processing and QA layer integrated into its real localization pipeline, with E2E verification, adversarial testing, regression coverage, and an honest record of what is and is not verified.**
