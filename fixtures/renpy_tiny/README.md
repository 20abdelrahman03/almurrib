# Tiny Ren'Py Fixture

A minimal, deterministic Ren'Py-style game directory used by the test
suite and by the CLI walkthrough in the docs.

Expected extraction result (11 entries total):

| File | Line | Kind | Speaker | Text |
|---|---|---|---|---|
| game/script.rpy | 8 | say | — | The wind blows over the empty street. |
| game/script.rpy | 9 | say | Eileen | Hello! Did you wait long? |
| game/script.rpy | 10 | say | Nadia | Not at all. I just arrived. |
| game/script.rpy | 11 | say | Eileen | Let's go inside. |
| game/script.rpy | 16 | menu | — | Follow Eileen |
| game/script.rpy | 17 | say | Nadia | I follow her quietly. |
| game/script.rpy | 18 | menu | — | Stay outside |
| game/script.rpy | 19 | say | Nadia | I need a moment alone. |
| game/script.rpy | 21 | say | Eileen | This is the end of the fixture. |
| game/script.rpy | 22 | say | Eileen | Your score is [score], {player_name}! |
| game/tl/arabic/strings.rpy | 4 | translate_strings | — | Tiny Fixture → اللعبة الصغيرة |

Line 22 exercises placeholder preservation (`[score]` Ren'Py substitution
and `{player_name}` Python-style formatting) through the whole pipeline.

Character *definitions* (`define e = Character("Eileen")`) and config
strings in `options.rpy` are intentionally not extracted.
