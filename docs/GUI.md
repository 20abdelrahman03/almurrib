# Almurrib Desktop GUI

A Tkinter desktop frontend for the Phase 1 workflow. It is a
**frontend only** — every action calls the existing `almurrib.core.workflow`
/ `almurrib.core.config` / `almurrib.providers` services. No localization
logic lives in the GUI.

Window title: **المعرب — Almurrib**

## Features

- Game folder picker (اختيار مجلد اللعبة) with native directory dialog
- Database path picker (anchored next to the EXE when packaged)
- Output folder picker (used consistently by Export and Localize)
- Source / target language dropdowns (target doubles as `tl/<lang>/`)
- Provider selector (20+ registry definitions, auto-fills Base URL)
- **Test Connection** (validates key, reports model count, never logs secrets)
- **Refresh Models** (live provider API first, LiteLLM/Models.dev fallback, source badge; searchable dropdown; manual id entry always works)
- **Force retranslation** checkbox (ignores TM/cache/translated, provider
  called again, provenance overwritten)
- **Clear Translations** (with confirmation) wipes stored translations for a clean-slate run; source entries and obsolete history stay, matching cache rows are dropped.
- Comparing models: Clear, pick model A, point Output Folder at out-model-a, Translate, Export; repeat for B, then diff the two strings.rpy files. (CLI: clear --game-dir ...)
- API key field is masked and **never written to the log**
- **Save Configuration** writes the on-screen values to the local `.env`
  (merges with existing keys, never deletes unmanaged ones)
- Buttons: **Detect**, **Extract**, **Translate**, **Export**, **LOCALIZE GAME**
- Progress bar: determinate during translation (real `done/total` from the
  translation stage), indeterminate for extract/export
- Log panel with `[INFO] / [OK] / [ERROR]` lines, right-click menu
  (Copy / Copy All / Select All / Clear), **Copy Log** (secrets redacted) and
  **Clear Log** buttons, auto-scroll
- Structured failure reports (provider, model, HTTP status, message,
  retries, suggestion) shown in the log and in an error dialog
- Long operations run on a background thread; buttons disable while running
  and the window stays responsive

## Where files live (packaged EXE)

When frozen, `.env`, the default database (`almurrib.db`) and the default
output (`out`) resolve next to `Almurrib.exe` — double-clicking from any
folder behaves the same. If the launch folder itself holds a `.env`, that
one wins (covers terminal launches from the project). During development
everything resolves to the working directory. Absolute paths typed into
the GUI always win. The log shows which config file was loaded at startup
(`config: ...`), and Save always writes next to the executable.

The model dropdown is never empty: every provider ships a curated fallback
list, replaced by the live catalog on **Refresh Models**. Resolution order
is live provider API → external catalog (LiteLLM / Models.dev) →
static fallback → manual entry; a **source badge** under the dropdown shows
which one produced the list, and selecting a model shows its metadata line
(context, JSON, reasoning, tools — Unknown when unavailable). Typing filters
the listed ids; custom ids are never rewritten (manual fallback for local,
private or brand-new models). A failed refresh keeps the previous working
list and shows the error instead of wiping it. Fresh catalogs are cached
next to the app (live 24h, external 7d); see [PROVIDERS.md](PROVIDERS.md).

## Run during development

```powershell
cd E:\المعرب
.\.venv\Scripts\python -m pip install -e ".[dev]"   # once
.\.venv\Scripts\almurrib-gui                         # or: python -m almurrib.gui.app
```

## Build the Windows executable

```powershell
cd E:\المعرب
.\.venv\Scripts\python build_exe.py
# → dist\Almurrib.exe   (windowed, single-file, ~13 MB)
```

Double-click `dist\Almurrib.exe` to launch the GUI — no Python or CLI needed.

## Notes / limitations

- Tkinter is used because it ships with CPython on Windows (no extra
  runtime dependency). This is intentionally a basic developer tool, not a
  polished UI.
- The GUI never logs or displays the saved API key; the field is masked and
  any accidental occurrence in a message is redacted before display.
- Full Arabic RTL/reshaping of the UI itself is a Phase 2 concern; the
  layout is kept simple and Arabic-friendly where practical.
- Building the exe requires PyInstaller (included in the `dev` extra).
