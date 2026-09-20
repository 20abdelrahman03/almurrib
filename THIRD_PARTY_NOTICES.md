# Third-Party Notices

المعرب (Almurrib) is licensed under AGPL-3.0 (see `LICENSE`).

## Runtime

The Phase 1 foundation has **no third-party runtime dependencies** — it
uses only the Python standard library (CPython, PSF License).

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
