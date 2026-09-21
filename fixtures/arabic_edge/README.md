# Arabic Edge Fixture

Deterministic Ren'Py-style game directory exercising Phase 2 Arabic
processing and QA through the real production path (extract → translate →
Arabic QA → persist → export → reparse).

Contents (`game/script.rpy`):

| Line(s) | Content kind |
|---|---|
| 8 | pure Arabic narrator line |
| 9 | mixed English + Arabic (`Hello مرحبا`) |
| 10 | Arabic with Latin digits (`125`) |
| 11 | placeholder (`{player_name}`) |
| 12 | markup (`<color=red>…</color>`) |
| 14–17 | greetings, model name (`Qwen3`), UI text (`HP: 100`) |
| 18 | Arabic punctuation + parentheses |
| 19 | escaped quotes |
| 20 | **deliberately untranslated English** (QA must flag it) |
| 21–25 | Arabic menu choices + dialogue |
| 26 | very long Arabic sentence (wrapping) |
| 27 | unbreakable long token (wrapping edge case) |

Expected E2E behavior with the test dictionary provider: every line
translates except line 20, which the provider echoes unchanged and Arabic
QA flags (`source_copied`, error). Placeholders, markup and newline escapes
survive byte-for-byte; the original fixture is never modified.
