# Third-Party Notices

المعرب (Almurrib) is licensed under AGPL-3.0 (see `LICENSE`).

## Runtime

Phase 1 was stdlib-only. Phase 2 adds exactly two small Unicode libraries
for the Arabic layer (pinned in `pyproject.toml`, no transitive
dependencies):

| Package | Version | License | Purpose |
|---|---|---|---|
| `arabic-reshaper` | 3.0.1 | MIT | Arabic presentation-form shaping (harakat preserved via explicit config) |
| `python-bidi` | 0.6.11 | LGPL-3.0 | Unicode Bidirectional Algorithm (visual order for legacy renderers) |
| `fontTools` | 4.65.0 | MIT | Font advance-width measurement for metric-aware wrapping (pure Python) |

## Optional extras (not installed by default)

| Package | Version | License | Purpose |
|---|---|---|---|
| `UnityPy` | 1.25.3 | MIT (K0lb3) | Unity asset parsing for the Unity adapter. Ships INSIDE `dist\Almurrib.exe` (with lz4/brotli/Pillow) so one-click Unity works with zero installs; source installs use the `almurrib[unity]` extra. Detection works without it. |
| `argostranslate` | 1.11.0 | MIT (Argos Open Tech) | Offline NMT for the Argos provider (`almurrib[offline]`). Heavy transitive stack (torch ~450MB, ctranslate2, stanza) stays out of the default install and EXE. Models (e.g. en→ar, ~88MB) download on explicit user command, never bundled. |

LGPL-3.0 is compatible with this project's AGPL-3.0-only license for
combined works. `python-bidi` 0.6.x ships a compiled Rust helper
(`bidi.cp312-win_amd64.pyd`); PyInstaller bundles it automatically
(verified in `dist\Almurrib.exe`). Everything else remains stdlib-only
(CPython, PSF License).

## Test fixtures

| Fixture | Source | License |
|---|---|---|
| `fixtures/renpy_tiny/` | created for this project | AGPL-3.0 |
| `fixtures/the_question/game/script.rpy` | Ren'Py demo "The Question" (github.com/renpy/renpy) | MIT |

## Development dependencies

| Package | License | Used for |
|---|---|---|
| pytest | MIT | test runner |
| iniconfig, pluggy, packaging, pygments, colorama | MIT / BSD | pytest transitive deps |

Dev dependencies are not distributed with the application and do not
affect the AGPL licensing of the runtime.

## Planned integrations (not yet included)

Future phases will integrate — through adapters, not vendored code —
open-source projects such as llama.cpp (MIT), CTranslate2 (MIT), Argos
Translate (MIT), UnityPy (MIT), repak (MIT), BepInEx (LGPL-2.1),
UABEA (GPL-3.0), AssetsTools.NET (MIT), VNTextPatch (GPL-3.0),
Velopack (MIT). Each integration will be reviewed for license
compatibility and recorded here with attribution before inclusion.
