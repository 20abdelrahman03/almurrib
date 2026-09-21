# RPG Maker MV/MZ Support (full)

**Status:** detect/extract/translate/build verified end-to-end on a
deterministic fixture. Runtime hooks: none needed (data-file patching).

## Detection

`www/data/System.json` (MV) or `data/System.json` (MZ), known data files,
`rpg_core.js` / `rmmz_core.js` markers. Variant reported in reasons.

## Extraction

* Maps: event Show-Text (401) with event-name speakers, choices (102).
* Database: actor/item/skill/... names, descriptions, profiles, messages.
* System: title, currency, basic/commands/params/messages terms.
* MapInfos names, CommonEvents, map display names.
* Skipped by design: JS plugin code (355/655), conditions/variables,
  tileset/animation metadata.

Every entry carries its JSON path (`events[i].pages[p].list[l]...`) for
exact write-back; ordinals keep ids deterministic.

## Build / patch

`write_data_patch` loads originals, sets translated values at recorded
paths, mirrors `www/data/...` (or `data/...`) under the output dir.
Untranslated entries keep source text; stale paths fail loudly with file
names (re-extract, then retry). Copy the patch over a game COPY to play.

## E2E

`tests/unit/test_rpgmaker.py` (11 tests incl. full workflow dispatch,
write-back round-trip, stale-path failure). Fixture:
`fixtures/rpgmaker_tiny/` (MV layout).
