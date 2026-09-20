# Almurrib Desktop GUI

A minimal Tkinter desktop frontend for the Phase 1 workflow. It is a
**frontend only** — every action calls the existing `almurrib.core.workflow`
/ `almurrib.core.config` / `almurrib.providers` services. No localization
logic lives in the GUI.

Window title: **المعرب — Almurrib**

## Features

- Game folder picker (اختيار مجلد اللعبة) with native directory dialog
- Database path picker (defaults to `almurrib.db`)
- Source / target language fields (defaults `en` / `arabic`)
- Provider configuration (provider, base URL, model, API key) — the API key
  field is masked and **never written to the log**
- **Save Configuration** writes a local `.env` (the existing config system)
- Buttons: **Detect**, **Extract**, **Translate**, **Export**, **LOCALIZE GAME**
- Progress bar: determinate during translation (real `done/total` from the
  translation stage), indeterminate for extract/export
- Read-only log panel with `[INFO] / [OK] / [ERROR]` lines
- Long operations run on a background thread; buttons disable while running
  and the window stays responsive

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
