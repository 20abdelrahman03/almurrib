# Phase 2 Manual Acceptance Test — Station 7 (click-by-click)

Acceptance fixture for glossary, gender/style context, glossary QA, font
metrics, wrapping, placeholders, mixed text, repeated runs and overlay.
Deterministic parts need no key and no money; one optional live experiment
uses your own provider/key.

## 0. Paths (exact)

```text
Browser game:   E:\المعرب\almurrib_phase2_manual_test\START_GAME.bat
Game source:    E:\المعرب\almurrib_phase2_manual_test\game_data\dialogue.json (72 nodes, 97 strings)
Glossary:       E:\المعرب\almurrib_phase2_manual_test\game_data\glossary.json (16 entries)
QA cases:       E:\المعرب\almurrib_phase2_manual_test\game_data\qa_cases.json (12 cases)
Ren'Py mirror:  E:\المعرب\almurrib_phase2_manual_test\rpy\game\script.rpy (generated, do not hand-edit)
Arabic output:  E:\المعرب\almurrib_phase2_manual_test\output\dialogue_ar.json
Almurrib GUI:   E:\المعرب\dist\Almurrib.exe  (or .\.venv\Scripts\almurrib-gui)
```

## 1. Play the English game (2 min)

1. Double-click `START_GAME.bat`. It tries Python first, else the
   built-in Windows server (`SERVE_GAME.ps1` — nothing to install), and
   opens the game only after a server is up.
   - Keep the **Station7 server** window OPEN while playing (closing it
     kills the game with `ERR_CONNECTION_REFUSED`).
   - If you see `ERR_CONNECTION_REFUSED`: read the server window (port
     busy? Python missing?).
   - No Python at all? No problem anymore — the Windows fallback needs
     nothing. (Installing Python 3 is still handy for the Almurrib CLI.)
2. Type a player name (or keep `Alex`), press **Start night shift**.
3. Click through dialogue, pick different choices, watch the **Debug panel**
   (ID, speaker, source, glossary matches, flags). Press **Restart** freely.
4. Expected: 72 reachable nodes, choices branch, `{player_name}` shows your
   name, no console errors (F12).

## 2. Localize with Almurrib — deterministic path ($0)

The `rpy/` mirror is already generated from `dialogue.json`
(`python tools/json_to_rpy.py` regenerates it). Glossary import is CLI:

```powershell
cd E:\المعرب
.\.venv\Scripts\python -c "import sys"  # (venv check, optional)
.\.venv\Scripts\almurrib glossary import --db manual_test.db --file almurrib_phase2_manual_test\game_data\glossary.json
.\.venv\Scripts\almurrib extract almurrib_phase2_manual_test\rpy --db manual_test.db
```

Then open the GUI (`dist\Almurrib.exe`) with these EXACT field values:

| Field (real label) | Value |
|---|---|
| Game Folder | `E:\المعرب\almurrib_phase2_manual_test\rpy` |
| Database | `E:\المعرب\manual_test.db` (Browse to it) |
| Output Folder | `E:\المعرب\almurrib_phase2_manual_test\output\almurrib_run` (Browse → New Folder) |
| Source | `English` |
| Target | `Arabic (ar)` |
| Provider | `OpenAI-Compatible (custom URL)` (or your provider; Base URL fills in) |
| Model | any (offline run ignores it — FakeProvider path below) |
| API Key | leave empty for the deterministic run |

Offline deterministic run (no key needed) is scripted:

```powershell
.\.venv\Scripts\python almurrib_phase2_manual_test\tools\run_deterministic.py
```

(It extracts, translates via the deterministic provider, exports
`strings.rpy`, and rebuilds `output/dialogue_ar.json` through
`tools/strings_to_ar_json.py`. `output/dialogue_ar.json` shipped in the
repo is that loop's product.)

## 3. Live experiment (optional, your key, your provider)

1. In the GUI set **Provider** (e.g. `Cohere`), **Fetch/Refresh Models**,
   pick a model, paste your **API Key**.
2. Press **Translate**, then **Export** (same Game Folder / Database /
   Output Folder as above).
3. Run the bridge on the fresh export:

```powershell
.\.venv\Scripts\python almurrib_phase2_manual_test\tools\strings_to_ar_json.py almurrib_phase2_manual_test\output\almurrib_run\game\tl\ar\strings.rpy -o almurrib_phase2_manual_test\output\dialogue_ar.json
```

4. Reload the browser game → **Arabic** mode shows real translations.

## 4. Test in the browser (checklist)

- [ ] English mode: full story plays, choices branch, debug panel fills.
- [ ] Arabic mode: translated lines show; missing ones fall back to English
      with "missing translation" note in the debug panel.
- [ ] Overlay mode: badge visible (`overlay ON — base: English, displayed:
      Arabic`), base locale line stays `English`.
- [ ] Debug panel shows glossary matches (e.g. `Sylvie -> سيلفي`) on name lines.
- [ ] `{player_name}` shows your typed name; `[score]` shows the score.
- [ ] RTL: Arabic text right-aligned.
- [ ] Reload after regeneration picks up new Arabic (cache-bust: hard reload).

## 5. QA failure cases (deliberate — supposed to flag)

Automated (no browser needed):

```powershell
.\.venv\Scripts\python -m pytest tests/integration/test_manual_fixture.py -q
```

Manual reading of `game_data/qa_cases.json` (`deliberate: true` rows):

| Case | Must flag |
|---|---|
| `qa_bad_name_003` (سيلفيا) | `glossary.forbidden` |
| `qa_forbidden_004` (المحطه) | `glossary.forbidden` |
| `qa_source_copy_005` | `source_copied` |
| `qa_suspicious_latin_006` | `suspicious_latin` (warning) |
| `qa_placeholder_missing_008` | `placeholder_missing` |
| `qa_bloated_010` | `excessive_length` (warning) |
| `qa_punct_011` (`مرحبا,`) | `english_punctuation` (warning) |

And must-NOT-flag: `qa_legit_latin_007` (OpenAI/Qwen3/API/FPS),
`qa_placeholder_kept_009`, `qa_arabic_punct_012`.

## 6. Repeated-run stability

In the GUI press **Translate → Export** twice: second run reports
`already=97, api=0`; the export file is byte-identical. Press **Clear
Translations** (confirm), then Translate again → full fresh provider run.

## 7. RTL UI check

In the Almurrib GUI press the `عربي` button: chrome flips to Arabic RTL;
press `EN` to switch back. Fields, model pool and log survive the switch.
(Core statistics stay English by design — universal units.)

## 8. What this proves (and does not)

- Automated here: fixture validity, bridge fidelity, QA expectations,
  glossary format, deterministic loop, repeated stability.
- Manual by you: browser play-through, overlay distinction, RTL UI feel.
- NOT proven: real-player translation quality (needs the live experiment),
  production browser-engine support (the `tools/*.py` bridge is an
  explicitly labeled test harness, not a Phase 3 adapter).
