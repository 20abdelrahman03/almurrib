# Phase 2 Status — Second 50% (glossary + metrics + RTL + overlay)

## Added in the second half

* Character/terminology glossary (model, gender/style, aliases, forbidden,
  enabled, project+global scopes, migration v3, JSON/CSV).
* Provider context (speaker traits + glossary terms in every prompt),
  glossary QA (names error / terms warning / forbidden error), cache
  scoping by glossary revision.
* Real font metrics (fontTools, pure Python) + bundled OFL Vazirmatn +
  metric-aware wrapping (unchanged wrap API).
* RTL UI foundation (i18n resource, LTR/RTL toggle with rebuild, Arabic
  chrome, English core stats) + overlay architecture (`core/overlay.py`;
  Ren'Py `ar` button documented as test-only mechanism).
* CLI `glossary` management; GUI auto-loads project glossaries.

## Prior half (kept green — archive)

## Implemented (first 50%)

* `arabic/` package: normalize, PUA-safe masking, reshape (harakat kept,
  idempotent), BiDi (per-paragraph, honestly non-idempotent), word wrap
  (atomic tokens, metrics abstraction), font foundation (no downloads).
* Structured QA engine: rules A–G + `register_qa_rule` glossary hook.
* Pipeline integration: NFC canonical storage, QA on every machine path,
  FLAGGED on errors, warnings on TRANSLATED, human states untouched.
* Fixtures: `arabic_edge/` (17-line edge game) + full E2E through
  production code (extract → translate → QA → persist → export → reparse).
* Adversarial (51), fuzz (600 seeded strings, placeholder invariant),
  failure injection, perf (75 lines / 0.16 s).

## Verified

* Offline unit/integration/E2E: full suite green (see final report).
* Production-path E2E on `the_question` (75) and `arabic_edge`.
* Byte-stable repeated runs; originals untouched.

## Rendering (verified during first half)

* Real Ren'Py engine rendering: VERIFIED 2026-09-21 on Ren'Py 8.5.3 SDK
  (the_question_ar_test, isolated copy): 77-pair strings.rpy + Vazirmatn
  font + native language button all render Arabic dialogue, menus and
  nameplates in-game (user-verified with screenshots).

## Deferred past Phase 2

* Tauri/React UI, other engines, runtime injection, TMX/XLIFF, LoRA.

## Dependencies (both halves)

`arabic-reshaper==3.0.1` (MIT), `python-bidi==0.6.11` (LGPL-3.0),
`fonttools==4.65.0` (MIT). Pinned in `pyproject.toml`; recorded in
THIRD_PARTY_NOTICES.md.

## Test commands

```powershell
.\.venv\Scripts\python -m pytest                          # offline suite
.\.venv\Scripts\python -m pytest tests\integration\test_arabic_e2e.py
.\.venv\Scripts\python -m pytest tests\integration\test_arabic_adversarial.py
.\.venv\Scripts\python build_exe.py                       # → dist\Almurrib.exe
```
