# Troubleshooting

## The game launches but stays English
* Ren'Py: pick the language in Preferences (the `ar` button exists only in
  our isolated test copy; real games list their own languages).
* Check the export actually contains pairs: open
  `out/game/tl/<lang>/strings.rpy` and look for `old`/`new` lines.
* `old` strings must match the game's runtime text byte-for-byte
  (escaped quotes are unescaped at extraction for exactly this reason).

## "No engine recognized"
* Ren'Py needs `game/` with `.rpy` (or packed `.rpa`) inside.
* RPG Maker needs `www/data/System.json` (MV) or `data/System.json` (MZ).
* Unity needs `*_Data/globalgamemanagers` (+ `.assets` for extraction).

## Translation shows 0/75 with failures
* Read the structured error (provider/model/HTTP/suggestion) — it names
  the cause (key, model id, rate limit, timeout).
* `401`: re-enter the key. `404`: Refresh Models and pick a listed id.
* `429`: wait, shrink batch size, or switch provider.

## GUI: empty model list
* Press **Refresh Models** (needs network + key, except local providers).
* Offline/manual: type any model id directly — it is never rewritten.

## EXE behaves differently than source runs
* The EXE reads `.env`/database/output next to itself; dev runs use the
  working directory. The GUI log prints the loaded config path at startup.
* UnityPy ships INSIDE the EXE (one-click Unity needs zero installs).
  Argos offline does NOT: use a desktop Python env with
  `almurrib[offline]` for that.

## Translation safety (canary, breaker, health)
* Jobs over ~100 pending entries start with a **[CANARY]** gate: 3 entries
  through the live provider. `FAIL` blocks the run before tokens burn.
* The progress bar counts **accepted** translations only (parsed + valid +
  QA-clean + staged). Requests/tokens/HTTP-200s never move it.
* 5 straight batches with zero accepted output (or 50k output tokens with
  zero accepted) **abort the run** with the first cause attached;
  untouched entries stay retryable. Nothing is half-saved.
* `translate --dry-run` prints counts, a measured token estimate and the
  canary verdict without translating.
* A rerun never resends cached successes (same provider/model).

## `force` vs `clear`
* `--force`/checkbox: ignore skips and re-call the provider (provenance
  overwritten). `clear`: wipe stored translations first (clean-slate
  model comparison). Neither touches source extraction.
