# Arabic QA Engine — Phase 2 (first 50%)

Structured flags (`QAFlag(rule_id, severity, message, evidence)`), never
bare strings. Stored as `rule:detail` tokens in `entry.qa_flags` (no schema
change), exported as `# QA:` comments. Errors → FLAGGED; warnings ride on
TRANSLATED. Human REVIEWED/APPROVED states are never touched by automatic QA.

## Rules

| ID | Severity | Fires when |
|---|---|---|
| `source_copied` | error | translation identical to source with localizable letters |
| `suspicious_latin` | warning | non-allowlisted Latin word (URLs/emails/versions/abbreviations exempt, max 5) |
| `no_arabic_script` | error | en→ar with zero Arabic script and localizable content |
| `english_punctuation` | warning | `, . ; ? ! :` in Arabic text (decimals, times, `HP:` labels, URLs exempt; suggests `، ؟ …`) |
| `placeholder_missing` | error | token lost (reuses core validator — single source of truth) |
| `placeholder_extra` | warning | new token invented by the model |
| `excessive_length` | warning | translation > 1.3× source (configurable) |
| `suspiciously_short` | warning | translation < 0.4× source (configurable) |
| `bidi_unbalanced` | warning | unbalanced `() [] {} «» “” ‘’` |
| `custom_rule_error` | warning | a custom rule crashed (engine never breaks on extensions) |

Allowlist: OpenAI, Qwen3, HP, FPS, DLC, Ren'Py…; ≤4-char UPPERCASE treated
as abbreviations; single Latin letters are NOT exempt.

## Extension (glossary hook)

`register_qa_rule(rule)` with the `QARule` protocol (`rule_id`, `check()`).
Name/gender/formality rules plug in here in Phase 2b — engine code needs no
changes.

## Pipeline position

```
provider batch → NFC normalize → placeholder validate → arabic_qa_check
→ persist (flags) → cache (placeholder-clean only) → export (comments)
```

QA also recomputes on TM/cache/already hits (machine states only, deduped
tokens), so flags always describe current text and repeated runs stay
byte-stable. Fresh API translations reset flags first (force-safe).
