# Almurrib — Phase 2 Manual Acceptance Test
## Build a Dense Local English Browser "Talking Game" Fixture

You are the implementation agent working inside the existing **Almurrib (المعرب)** repository.

Phase 2 is complete according to the current implementation report:

- Arabic processing
- Arabic QA
- Character/terminology glossary
- Gender/style translation context
- Real font metrics
- RTL-capable Almurrib UI
- Localization overlay architecture
- 352 tests passing
- EXE builds successfully

We now need a **human-facing acceptance test** for the second half of Phase 2.

Your job is to build a small but realistically **dense English-speaking browser game/test fixture** that runs completely locally, requires no backend, and gives the user realistic material to exercise:

- glossary matching
- character names
- gender/style context
- glossary-aware QA
- long Arabic translations
- real font metrics
- Arabic-aware wrapping
- placeholders
- mixed Arabic/English
- numbers
- punctuation
- URLs
- repeated terminology
- repeated translation runs
- visible English → Arabic output

The game can be silly. It does not need graphics. The value is in the text, metadata, branches, and testability.

---

# 1. FIRST: INSPECT THE REAL ALMURRIB PROJECT

Before coding anything, inspect the current repository and determine:

- what input file formats Almurrib actually supports today
- what the current CLI supports
- what the current GUI fields are called
- how the glossary is currently stored and loaded
- how glossary context reaches providers
- how Arabic QA is invoked
- what export formats exist
- what can be tested without implementing Phase 3
- whether HTML/JSON can be consumed directly by the current pipeline
- whether a tiny test-only bridge is needed

Do **not** invent unsupported instructions.

If Almurrib does not currently support HTML/JS as an engine, do **not** build a production web-engine adapter.

Instead:

- make the browser game the human-facing source of truth
- create a small local data fixture that mirrors its dialogue
- use the current supported Almurrib workflow for that fixture, or create only the smallest test harness/bridge necessary for Phase 2 acceptance testing
- clearly distinguish this test harness from a future production engine adapter

---

# 2. CORE GAME REQUIREMENT

Create a local browser game using simple:

```text
HTML
CSS
JavaScript
```

Prefer zero external runtime dependencies.

The user should be able to launch it locally with either:

```text
double-click START_GAME.bat
```

or:

```powershell
python -m http.server
```

Do not require a backend.

If `file://` causes browser restrictions, provide:

```text
START_GAME.bat
```

that starts a tiny local static server with Python's standard library and opens the browser.

No internet connection should be required.

---

# 3. GAME CONCEPT

Create a small but coherent "talking game".

Example themes:

- "Professor Potato's Extremely Serious Interview"
- "The Midnight Conversation at Station 7"
- "The World's Least Competent Space Mission"

Choose whatever is funniest and easiest to localize.

The game should feel like a real tiny dialogue game for several minutes.

It should have:

- beginning
- middle
- several branches
- recurring characters
- recurring terminology
- simple state/variables
- 60–100 content entries

No need for sophisticated graphics.

---

# 4. CHARACTERS

Use at least 4 recurring characters.

For example:

```text
Sylvie
Professor Hale
Mira
Captain Rowan
```

Give each a distinctive speaking style.

Example:

```text
Sylvie = casual/friendly/female
Professor Hale = formal/technical
Mira = sarcastic
Captain Rowan = commanding/polite
```

Names must occur repeatedly throughout the dialogue so the glossary has meaningful work to do.

---

# 5. DIALOGUE CONTENT

Create roughly **60–100 source entries**.

Include all of the following:

## Normal dialogue

```text
"Good evening. I thought you were going to be late."
```

## Very short dialogue

```text
"Sure."
```

## Long dialogue

Several sentences/paragraphs that meaningfully stress wrapping.

## Choices

At least 10 choice points, such as:

```text
Ask about the station.
Ask about the professor.
Leave quietly.
```

The selected choice should affect a small amount of state or branch.

## Repeated names

Characters should speak many times.

## Repeated terminology

Use terminology such as:

```text
visual novel
control room
archive key
night shift
station protocol
emergency channel
```

## Numbers

Include:

```text
7
42
1998
3.14
100%
```

## Legitimate Latin tokens

Include deliberate valid examples such as:

```text
OpenAI
Qwen3
API
FPS
HTTP
JSON
```

These must remain valid test cases for QA.

## URLs

Include one or two strings like:

```text
https://example.com/station/alpha
```

## Placeholders

Use the placeholder syntax that the **current Almurrib pipeline actually supports**.

Examples if compatible:

```text
{name}
{player_name}
{count}
```

Do not invent unsupported placeholder syntax.

## Punctuation

Include:

```text
?
!
:
;
()
[]
...
```

## Markup-like content

Only use markup syntax already compatible with the current Almurrib implementation.

Do not invent arbitrary markup that the current pipeline cannot preserve.

---

# 6. GENDER-SENSITIVE CONTENT

Add sentences where gender/context matters.

For example:

```text
Sylvie is tired.
Sylvie said she was ready.
Professor Hale thanked her.
Mira sounded annoyed.
Captain Rowan told him to wait.
```

Include contextual lines such as:

```text
"I'm ready."
"I'm not ready."
"Are you sure?"
"You're late."
"I knew you would come back."
```

The goal is to exercise the new `TranslationContext`.

---

# 7. TEST GLOSSARY

Create a fixture glossary using the **real current Almurrib glossary format**.

It should contain at least 15 entries.

Example concepts:

```text
Sylvie -> سيلفي
Professor Hale -> البروفيسور هيل
Mira -> ميرا
Captain Rowan -> القائد روان
visual novel -> رواية بصرية
control room -> غرفة التحكم
archive key -> مفتاح الأرشيف
night shift -> النوبة الليلية
station protocol -> بروتوكول المحطة
emergency channel -> قناة الطوارئ
```

Include:

- character entries
- term entries
- gender metadata
- style/register metadata
- aliases where useful
- at least 2 forbidden target variants
- at least 2 overlapping/edge-case entries

Do not make up a new glossary schema if the repository already has one.

---

# 8. INTENTIONAL QA CASES

Create deliberate pass/fail cases so the user can verify QA.

Use a format compatible with the current project, such as:

```text
qa_cases.json
```

or another appropriate fixture format.

Include:

## Expected pass

Correct character name:

```text
Sylvie -> سيلفي
```

Correct terminology:

```text
visual novel -> رواية بصرية
```

## Expected glossary mismatch

```text
سيلفيه
```

## Expected forbidden-term violation

Use a deliberately forbidden target variant.

## Expected source-copy

Leave English unchanged.

## Suspicious Latin

An Arabic translation that still contains too much English.

## Legitimate Latin

Examples:

```text
OpenAI
Qwen3
API
FPS
```

Ensure these demonstrate that QA does not blindly reject every Latin token.

## Placeholder missing

Deliberately remove `{name}`.

## Placeholder preserved

Keep `{name}` exactly.

## Excessive length

Create an intentionally bloated Arabic translation.

## Punctuation case

Use English punctuation inside an Arabic sentence.

Use the **actual current QA implementation** and document exactly which cases should be flagged and why.

---

# 9. SHARED SOURCE DATA

The browser game should load its dialogue from data files rather than hard-code every line in JavaScript.

Prefer a structure such as:

```text
game_data/
    dialogue.json
    glossary.json
    qa_cases.json
```

The exact structure can differ if the current Almurrib workflow suggests a better fit.

Each dialogue entry should preserve:

- stable ID
- speaker
- source English text
- context
- choices where applicable
- metadata

Example conceptual shape:

```json
{
  "id": "dlg_001",
  "speaker": "Sylvie",
  "text": "Good evening. I thought you were going to be late.",
  "context": "station platform"
}
```

Align this as closely as practical with the current `LocalizationEntry` model.

---

# 10. ARABIC OUTPUT MUST BE SEPARATE

Never overwrite the English source.

Create a separate Arabic output location, for example:

```text
dialogue_ar.json
```

or the exact output format supported by the current Almurrib workflow.

The browser harness should be capable of loading:

```text
English source
```

or:

```text
Arabic output
```

for comparison.

---

# 11. OVERLAY DEMONSTRATION

Add a third test mode in the browser harness:

```text
Base Locale: English
Displayed Localization: Arabic
Overlay: ON
```

This should be a **simulation of Almurrib's overlay architecture**, not a Phase 3 runtime implementation.

It should demonstrate conceptually:

```text
game base language = English
        ↓
Arabic overlay
        ↓
visible text = Arabic
```

The test harness can therefore have:

```text
Mode:
[English]
[Arabic]
[English base + Arabic overlay]
```

Clearly label this as a Phase 2 conceptual test.

---

# 12. TEST/DEBUG PANEL

Add a simple developer panel.

Show:

```text
Dialogue ID
Speaker
Original English
Current displayed text
Glossary matches
Base Locale
Displayed Localization
Overlay State
```

This makes manual testing concrete.

Do not over-engineer it.

---

# 13. HOW ALMURRIB SHOULD BE USED

Create:

```text
docs/PHASE2_MANUAL_TEST.md
```

This document is **critical**.

It must tell the user exactly:

1. which `.bat` to run to start the browser game
2. which folder to open in Almurrib
3. which source file to select
4. which database/project to choose
5. which glossary file to load
6. source language
7. target language
8. provider
9. model
10. API key field handling, if needed
11. output directory
12. which generated file to inspect
13. how to load the generated Arabic into the browser harness
14. which test cases to click/play
15. what the user should expect

Do not say merely "test it".

Make this a literal click-by-click/manual procedure based on the **actual current GUI**.

---

# 14. EXACT PATHS MUST BE GIVEN

The final instructions must contain real exact paths like:

```text
Browser game:
E:\...\START_GAME.bat

Game source:
E:\...\game_data\dialogue.json

Glossary:
E:\...\game_data\glossary.json

QA cases:
E:\...\game_data\qa_cases.json

Arabic output:
E:\...\output\dialogue_ar.json
```

Use the actual repository path discovered during implementation.

If a path differs, use the actual path.

---

# 15. USE THE ACTUAL ALMURRIB GUI

If the current GUI has fields like:

```text
Game Folder
Database
Source Language
Target Language
Provider
Model
API Key
Output Directory
```

then document the exact value for every field.

If the GUI uses different fields now, use the real labels.

Also provide exact CLI commands if the workflow supports them.

---

# 16. DETERMINISTIC PROVIDER

For acceptance testing, prefer a deterministic/local/mock provider that is already supported.

The user should not need to spend money merely to verify:

- glossary flow
- QA
- font metrics
- wrapping
- persistence
- output generation

If a live model is necessary for one experiment, clearly separate it from the deterministic acceptance test.

Never require the user to paste an API key into a source file.

---

# 17. EXPECTED RESULT CHECKLIST

The manual test document must include a checklist like:

```text
[ ] Browser game launches locally
[ ] 60–100 source entries are present
[ ] Characters recur correctly
[ ] Glossary loads
[ ] Glossary matches are visible
[ ] Gender/style context is visible or traceable
[ ] Glossary mismatch is flagged
[ ] Forbidden term is flagged
[ ] Source-copy is flagged
[ ] Legitimate Latin tokens are not blindly rejected
[ ] Placeholders survive
[ ] Long Arabic text wraps correctly
[ ] Real font metrics are used
[ ] English source remains untouched
[ ] Arabic output is stored separately
[ ] Repeated run is stable
[ ] Overlay mode reports English base + Arabic displayed
[ ] Almurrib RTL UI works
[ ] UI can switch back to English
```

---

# 18. DELIBERATE FAILURE CASES

Clearly mark cases that are **supposed to fail**.

Example names:

```text
qa_bad_name_001
qa_placeholder_missing_002
qa_forbidden_term_003
qa_source_copy_004
```

The user should know:

> This case is supposed to be flagged.

This prevents false conclusions.

---

# 19. BROWSER TEST FLOW

The browser game should expose enough UI so the user can:

### A. Play the English version

See the original English text.

### B. Play the Arabic version

See Almurrib's generated Arabic output.

### C. Turn on overlay mode

Verify the conceptual distinction:

```text
Base Locale = English
Displayed = Arabic
Overlay = ON
```

### D. Inspect developer data

Click a dialogue line and see:

```text
Speaker
Source text
Displayed text
Glossary matches
```

---

# 20. TEST THE TEST FIXTURE

Before handing it to the user:

Verify:

- browser game launches
- no internet is required
- no backend is required
- all English dialogue loads
- choices work
- state/branches work
- placeholders are handled safely
- fixture files parse
- glossary format is valid
- QA cases are valid
- Almurrib can consume the chosen fixture workflow
- generated Arabic can be loaded into the browser harness
- English source remains untouched
- the output can be compared with the source

If the current Almurrib cannot directly consume the browser source, clearly implement/document the smallest Phase-2 test bridge and state that it is only a test harness, not a production engine adapter.

---

# 21. NO PHASE 3

Do NOT implement:

- Unity
- Unreal
- RPG Maker
- BepInEx
- UE4SS
- VNTextPatch
- runtime injection
- production browser engine adapter
- other new production engine adapters

This task is strictly a **Phase 2 manual acceptance-test fixture**.

---

# 22. FINAL REPORT

Return:

## 1. What Was Built
Theme, game flow, number of entries, characters, choices.

## 2. Exact Files
Every important file and exact path.

## 3. How to Launch
Exact command or `.bat`.

## 4. How to Use Almurrib
Exact step-by-step workflow.

## 5. Exact Files to Select
Source, glossary, QA cases, database, output.

## 6. Expected Results
What should happen at each step.

## 7. Deliberate Failure Cases
Which cases should be flagged.

## 8. What This Test Proves
Separate:
- automated
- manually verified
- not verified

## 9. Known Limitations
Be honest.

---

# 23. SUCCESS CONDITION

The user should end up with something conceptually like:

```text
almurrib_phase2_manual_test/
│
├── game/
│   ├── index.html
│   ├── styles.css
│   └── app.js
│
├── game_data/
│   ├── dialogue.json
│   ├── glossary.json
│   └── qa_cases.json
│
├── output/
│   └── dialogue_ar.json
│
├── START_GAME.bat
├── docs/
│   └── PHASE2_MANUAL_TEST.md
└── README.md
```

The exact structure may differ based on the current project architecture.

The user's experience should be:

```text
1. Run START_GAME.bat
2. Play the English game
3. Close it
4. Open Almurrib
5. Select the exact source file/path
6. Load the exact glossary
7. Run the deterministic localization workflow
8. Inspect the generated Arabic output
9. Open the browser harness in Arabic mode
10. Test overlay mode
11. Run the documented QA failure cases
12. Compare results against the checklist
```

The final handoff must be detailed enough that the user never has to guess:

- which file to select
- which folder to use
- which glossary to load
- where the output is
- what success looks like

---

# ABSOLUTE RULES

1. This is a Phase 2 acceptance-test fixture.
2. Do not start Phase 3.
3. Inspect the real current project before designing the workflow.
4. Do not invent unsupported Almurrib GUI/CLI behavior.
5. Keep the English source intact.
6. Never overwrite the original English with Arabic.
7. Keep generated Arabic separate.
8. Use the real current glossary format.
9. Use the real current GUI/CLI labels.
10. Prefer deterministic testing.
11. Include intentional QA failures.
12. Explain expected results exactly.
13. Do not expose secrets.
14. Do not commit unless explicitly requested.
15. Be honest about what the fixture proves and what it does not prove.
