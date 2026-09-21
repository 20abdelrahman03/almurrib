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
* Unity/Argos extras are NOT in the EXE: use a desktop Python env with
  `almurrib[unity]` / `almurrib[offline]`.

## `force` vs `clear`
* `--force`/checkbox: ignore skips and re-call the provider (provenance
  overwritten). `clear`: wipe stored translations first (clean-slate
  model comparison). Neither touches source extraction.
