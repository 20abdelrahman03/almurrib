# Phase 3 Architecture (as built)

```
GUI (Simple default / Advanced) / CLI
        |
Workflow / Pipeline (engine-agnostic, authoritative)
        |
Core domain (entries, glossary, QA, cache/TM, provenance, overlay)
        |
Arabic layer (normalize/mask/reshape/BiDi/wrap/fonts/metrics)
        |
Providers (registry + generic OpenAI transport + Cohere/Argos native +
           llama.cpp lifecycle; cloud optional, offline real)
        |
Engine adapters (Ren'Py + RPG Maker + Unity/optional; capability table)
        |
Export (per-engine dispatch: string patch / data patch / asset rebuild)
```

Rules that survived contact with new engines:

* No engine `if/elif` in core (dispatch lives in `engine_adapters/`).
* Shared shapes (`RawStatement`, `TranslationContext`, `ModelInfo`) over
  per-engine concepts; new kinds are strings, never core changes.
* Storage behind repositories; migrations append-only (now v4).
* Heavy/native stacks are optional extras, never default/EXE weight.
* Canonical logical text is never replaced by render-ready text.
* Base game locale stays English; Arabic arrives as overlay/patch.
