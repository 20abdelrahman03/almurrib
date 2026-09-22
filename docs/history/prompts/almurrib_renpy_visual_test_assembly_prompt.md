# Almurrib — Phase 2 Real Ren'Py Rendering Test Assembly
## Mission: Prepare the complete isolated test environment — DO NOT run the game

You are the implementation agent working inside the existing **Almurrib (المعرب)** repository.

Phase 2 first 50% is implemented and the automated report says:

- 290 passed, 0 failed
- 2 live tests skipped by design
- Arabic layer implemented
- Arabic QA implemented
- Ren'Py export implemented
- Real Ren'Py visual rendering is still **UNVERIFIED**

Your job is to **find the existing Ren'Py SDK/test game, create a safe isolated test copy, inject the Almurrib-generated Arabic localization and any required font/resource files, verify the assembled test directory structurally, and then STOP.**

The user will perform the visual test manually.

---

## 1. Non-negotiable rules

1. **DO NOT launch `renpy.exe`.**
2. **DO NOT launch the Ren'Py game.**
3. **DO NOT claim visual rendering is verified.**
4. Never modify the original Ren'Py SDK project destructively.
5. Never modify the original Almurrib fixture destructively.
6. Work only in a new isolated test copy.
7. Preserve existing user work.
8. Do not reset/revert unrelated Git changes.
9. Do not commit anything.
10. Never expose or copy secrets/API keys.
11. Prefer copying over moving.
12. If a required asset is missing, report it honestly.

---

## 2. Known paths

Almurrib repository:

```text
E:\المعرب\
```

Current generated Ren'Py localization:

```text
E:\المعرب\dist\out\game\tl\ar\strings.rpy
```

Smaller fixture, NOT the primary visual test:

```text
E:\المعرب\fixtures\renpy_tiny\game\tl\arabic\strings.rpy
```

The real test game is:

```text
the_question
```

inside the downloaded Ren'Py SDK.

---

## 3. Reconnaissance first

Inspect:

```text
E:\المعرب\
```

and locate:

- Almurrib repository root
- `dist\out\game\tl\ar\strings.rpy`
- existing Arabic/font resources
- Git status

Then locate the **Ren'Py SDK** by searching for:

```text
renpy.exe
```

Prefer the SDK containing:

```text
docguilauncherlibrenpyrenpy.appsdk-fontsthe_questiontutorialupdateLICENSE.txt
renpy.exe
renpy.py
renpy.sh
```

If multiple SDKs exist:

- prefer the one containing `the_question`
- report the selected SDK
- do not modify the original SDK project

---

## 4. Create an isolated test project

Create a new directory, preferably:

```text
E:\المعرب\dist\renpy_visual_test\
```

Inside it create a recursive copy of the SDK's:

```text
the_question
```

as:

```text
the_question_ar_test
```

Conceptually:

```text
renpy_visual_test└── the_question_ar_test    ├── game    └── ...
```

Do not alter the SDK's original `the_question`.

---

## 5. Verify the copied game

Inspect the copied project and confirm it is a valid Ren'Py project and is actually the expected `the_question` fixture.

Record what proves this.

---

## 6. Inject the Almurrib translation

Copy:

```text
E:\المعرب\dist\out\game\tl\ar\strings.rpy
```

to:

```text
the_question_ar_test\game\tl\ar\strings.rpy
```

Create missing directories safely.

If an existing file is present:

- inspect it first
- do not blindly overwrite an unrelated file
- make sure the final file is the intended Almurrib-generated file

---

## 7. Check language discovery

Inspect the copied project for existing Ren'Py language configuration.

Determine whether:

```text
game\tl\ar\strings.rpy
```

is sufficient for Ren'Py to discover the translation.

If a small configuration change is necessary, apply it **only inside the isolated copy** and document it.

Do not guess or modify the original SDK project.

---

## 8. Prepare an Arabic font/resource

Inspect Almurrib first for already-prepared fonts:

```text
Vazirmatn
Lalezar
Noto Naskh
Cairo
Amiri
.ttf
.otf
```

Preferred order:

### A. Existing Almurrib font
Use it.

### B. Suitable font already in the Ren'Py project/SDK
Use it if appropriate for Arabic.

### C. No suitable font
If internet access is available and downloading is appropriate, obtain **Vazirmatn** from a reputable/official source, verify its license, and stage it locally inside the isolated test project.

Do not download random font packs.

If downloading is unavailable or inappropriate, continue assembling the test but clearly mark the font as missing.

Do not globally install fonts into Windows unless strictly necessary. Prefer project-local resources.

---

## 9. Configure the font safely

If the chosen font needs to be referenced by Ren'Py:

- configure it only in the isolated test project
- use the project-local font path
- document the exact file changed
- document font name, path, and license/source

Do not modify the original SDK project.

---

## 10. Create a test manifest

Before/after modifications, create a small manifest such as:

```text
renpy_visual_test_manifest.json
```

Record at least:

```json
{
  "almurrib_source": "...",
  "renpy_sdk": "...",
  "test_project": "...",
  "translation_file": "...",
  "font_file": "...",
  "launched_by_agent": false
}
```

Exact schema is your choice.

---

## 11. Structural verification — no launch

Verify:

### Translation
- `strings.rpy` exists
- non-empty
- valid text
- contains expected Ren'Py translation blocks
- contains expected Arabic translations

### Project
- copied `the_question_ar_test` has normal Ren'Py structure

### Language
- `game/tl/ar/` exists
- no accidental `game/tl/ar/ar/strings.rpy`

### Font
- selected font exists if staged
- configured references point to the correct local path

### Safety
- original SDK `the_question` is unchanged
- original Almurrib fixtures are unchanged
- no destructive edits happened outside the isolated test directory

Static/parser checks are allowed.

**Do not launch Ren'Py.**

---

## 12. Optional manual launcher

If useful, create:

```text
START_RENPY_TEST.bat
```

Its only purpose is to let the user launch the isolated test later.

The implementation agent must NOT execute this launcher.

Do not put destructive actions inside it.

---

## 13. Final handoff report

Return:

### Paths

```text
Ren'Py SDK:
<path>

Isolated test project:
<path>

Injected translation:
<path>

Font:
<path or MISSING>

Launcher:
<path or NONE>
```

### Changes made
Exactly what was copied/modified.

### Verification

Use explicit statuses such as:

```text
strings.rpy: READY
Arabic path: READY
Font: READY / MISSING
Project copy: READY
Original project untouched: VERIFIED
Ren'Py launched by agent: NO
Visual rendering: UNVERIFIED
```

### User next action
Tell the user exactly which launcher or `renpy.exe` to open and which isolated project to select.

Do not perform that action yourself.

---

## 14. Failure handling

If assembly cannot be completed:

- stop safely
- do not modify unrelated files
- report the exact blocker
- report the exact missing path/resource
- do not claim readiness

---

## 15. Success condition

The user must end up with:

```text
Ren'Py the_question
        +
Almurrib generated Arabic strings.rpy
        +
Arabic font/resource (when available)
        +
required local language configuration
        ↓
ready for manual visual testing
```

Final status must explicitly be:

> **READY FOR MANUAL REN'PY VISUAL TEST — NOT LAUNCHED BY AGENT**
