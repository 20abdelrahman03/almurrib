# Arabic Layer — Phase 2 (first 50%)

Engine-independent Arabic processing (`src/almurrib/arabic/`): normalization,
reshaping, BiDi, word wrapping, font foundation. GUI-independent,
provider-independent, reusable by future engine adapters.

## The one rule

```text
canonical (logical) text  →  stored in SQLite, exported to Ren'Py
render-ready (visual) text →  derived on demand, NEVER stored
```

Ren'Py/HarfBuzz shape and reorder Arabic themselves; feeding them
pre-shaped text double-shapes it. `to_visual()` exists only for legacy
renderers without a shaping stack.

## Modules

| Module | Responsibility |
|---|---|
| `normalize.py` | NFC (+ safe whitespace/control hygiene). Keeps tatweel, diacritics, ZWJ/ZWNJ, digits, directional marks. |
| `masking.py` | Masks `{x}`/`%s`/`[v]`/`<b>` as distinct PUA sentinels (BiDi class L), restored by character — order-safe by construction. python-bidi **rejects** LRI/PDI isolates (verified crash), hence PUA. |
| `reshape.py` | `arabic-reshaper` with `delete_harakat=False` (upstream default strips vowels — we override). `is_shaped()` guard: never shapes twice (idempotent, verified). |
| `bidi.py` | `get_display` per-paragraph wrapper. NOT idempotent (verified): visual output must always derive from logical text. |
| `wrap.py` | Greedy wrap on `TextMetrics` (default: 1 unit/char fallback). Protected tokens atomic (own line on overflow, never split). Paragraphs never merge. `max_width < 1` raises. |
| `fonts.py` | `FontAsset` (license defaults to Unknown, never guessed) + `FontRegistry` scan/manifest. No downloads, no injection yet. |

## Dependencies

`arabic-reshaper==3.0.1` (MIT) + `python-bidi==0.6.11` (LGPL-3.0, compatible
with AGPL-3.0). Both pinned; no transitive deps. See THIRD_PARTY_NOTICES.

## Verified behaviors

* reshape idempotent; bidi/to_visual NOT idempotent (documented, tested).
* Placeholder set invariant holds across all passes (300-string fuzz).
* 75 game lines process in ~0.16 s (measured; see test_arabic_perf).

## Known limitations

* Char-count metrics ≠ rendered width (needs font metrics — Phase 2b).
* No real-engine rendering check (no Ren'Py runtime here): UNVERIFIED.
* Mirroring nuance: masking treats tokens as LTR units (correct for our
  ASCII token set).
