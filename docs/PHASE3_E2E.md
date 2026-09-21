# Phase 3 E2E (what runs green)

* Ren'Py: 77-entry fixture + the_question through detect → extract →
  translate → QA → export → reparse; packed `.rpa` synthetic archives;
  real-engine render verified earlier (isolated 8.5.3 test).
* RPG Maker MV: 32-entry fixture through the same shared workflow
  (extract → translate → data-patch export → JSON round-trip read).
* Unity full-stack milestone: structured analysis + 12-capability profiles
  (calibrated on Hollow Knight vs Slender); candidate classification;
  language-sheet split + element write-back with real-blob round-trip
  (0 neighbors disturbed); workspace/manifest/rollback; tool registry
  (researched versions); XUnity bundle with source-verified escaping;
  `localize_unity_game` service E2E (fake UnityPy + FakeProvider);
  CLI `unity` group + GUI one-click panel; docs + support matrix.
  Real-game extraction VERIFIED on Hollow Knight (Unity 0.85, 1004 assets,
  4092 clean entries = 4089 EN language-sheet entries + 3 legit blobs,
  ~20s; binary-blob filter, full entity unescape incl. `&#39;`, engine
  markup like `<page>` placeholder-protected). Slender 2012: detected,
  Mono-DLL text correctly out of scope. Sheet write-back is next.
* Glossary: seed → context → provider → QA → persist → export → reparse
  on the_question; cache-veto precision (only violating entries re-hit).
* Offline: Argos en→ar real translations (model present) or clean skips.
* Repeated runs: byte-stable exports; force reprocesses; clear resets.
* Browser fixture: EN/AR/overlay modes, debug panel, 72/72 reachable.
* EXE: builds, launches outside repo cwd, window responds.
