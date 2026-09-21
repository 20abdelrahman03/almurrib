"""Structured Arabic QA engine (rules A–G + glossary extension point).

Every rule returns explainable flags — never bare strings — with a stable
``rule_id``, a severity (``error`` | ``warning`` | ``info``), a message and
the offending evidence. The translation stage maps errors to FLAGGED and
keeps warnings on TRANSLATED entries (visible in export comments).

Design rules:

* No rule fires on placeholders/markup/URLs/emails/model ids — those are
  stripped before language heuristics run.
* Unknown is acceptable: heuristics carry reason codes; aggressive guesses
  are ``info``, never ``error``.
* Glossary-aware rules (names, gender, formality) plug in through
  :func:`register_qa_rule` — the engine is closed for modification of the
  core set, open for extension.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from almurrib.arabic.normalize import contains_arabic
from almurrib.core.placeholders import extract_placeholders, validate_translation

_SEVERITIES = ("error", "warning", "info")


@dataclass(frozen=True)
class QAFlag:
    rule_id: str
    severity: str  # error | warning | info
    message: str
    evidence: str = ""

    def __post_init__(self) -> None:
        if self.severity not in _SEVERITIES:
            raise ValueError(f"bad severity: {self.severity!r}")

    def storage_token(self) -> str:
        """Compact ``rule: detail`` token stored in entry.qa_flags."""
        detail = self.evidence or self.message
        return f"{self.rule_id}:{detail}"


@dataclass
class QAResult:
    entry_id: str | None = None
    passed: bool = True  # no error-severity flags
    flags: list[QAFlag] = field(default_factory=list)

    def errors(self) -> list[QAFlag]:
        return [f for f in self.flags if f.severity == "error"]


class QARule(Protocol):
    """Future glossary-aware (or custom) rules implement this."""

    rule_id: str

    def check(
        self, source_text: str, translated_text: str, *, target_lang: str
    ) -> list[QAFlag]: ...


CUSTOM_RULES: list[QARule] = []


def register_qa_rule(rule: QARule) -> QARule:
    """Extension hook for glossary/name/gender/formality rules (Phase 2b)."""
    CUSTOM_RULES.append(rule)
    return rule


# -- shared scrubbing ---------------------------------------------------------

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_VERSION_RE = re.compile(r"\bv?\d+(?:\.\d+)+\b")  # 1.2, v2.5 ...
_DECIMAL_RE = re.compile(r"\d+[.,]\d+")
_DIGIT_RUN_RE = re.compile(r"\d+")

# Abbreviations / product terms that are legitimately Latin in Arabic text.
LATIN_ALLOWLIST = frozenset({
    "openai", "qwen3", "qwen", "hp", "fps", "dlc", "renpy", "rpg",
    "ok", "yes", "no", "tv", "pc", "ai", "ui", "os", "gb", "mb",
})


def _strip_neutral(text: str, *, placeholders: list[str]) -> str:
    """Remove tokens no language heuristic may judge."""
    out = text
    for token in sorted(set(placeholders), key=len, reverse=True):
        out = out.replace(token, " ")
    out = _URL_RE.sub(" ", out)
    out = _EMAIL_RE.sub(" ", out)
    return out


def _latin_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9'_-]*", text)


def _is_placeholder_only(text: str) -> bool:
    """True when nothing remains after removing protected tokens."""
    remainder = text
    for token in sorted(set(extract_placeholders(text)), key=len, reverse=True):
        remainder = remainder.replace(token, "")
    return not re.search(r"[A-Za-z\u0600-\u06FF]", remainder)


def _nothing_to_localize(text: str) -> bool:
    """True when the text holds no localizable letters.

    Placeholder-only strings, digits/punct, and short ALL-CAPS codes
    (``HP: 100``) legitimately stay untranslated. Single Latin letters do
    NOT qualify (``A``/``I`` must translate or be reviewed).
    """
    remainder = text
    for token in sorted(set(extract_placeholders(text)), key=len, reverse=True):
        remainder = remainder.replace(token, "")
    remainder = _URL_RE.sub(" ", remainder)
    remainder = _EMAIL_RE.sub(" ", remainder)
    if re.search(r"[a-z\u0600-\u06FF]", remainder):
        return False
    for word in _latin_words(remainder):
        if word.lower() in LATIN_ALLOWLIST:
            continue
        if 1 < len(word) <= 4 and word.isupper():
            continue  # probable abbreviation (HP, FPS, DLC)
        return False
    return True


# -- rule A: source copied unchanged --------------------------------------------

def _rule_source_copied(source: str, translation: str) -> list[QAFlag]:
    if not translation or source != translation:
        return []
    if contains_arabic(translation):
        return []  # already Arabic script: nothing left to localize
    if _nothing_to_localize(source):
        return []  # codes/placeholders/digits: copying is correct
    return [QAFlag("source_copied", "error",
                   "translation identical to source", source[:80])]


# -- rule B: suspicious Latin -----------------------------------------------------

def _rule_suspicious_latin(source: str, translation: str) -> list[QAFlag]:
    cleaned = _strip_neutral(translation, placeholders=extract_placeholders(translation))
    cleaned = _VERSION_RE.sub(" ", cleaned)
    cleaned = _DECIMAL_RE.sub(" ", cleaned)
    flags: list[QAFlag] = []
    for word in _latin_words(cleaned):
        lowered = word.lower()
        if lowered in LATIN_ALLOWLIST:
            continue  # allowlisted product/abbreviation
        if len(word) <= 4 and word.isupper():
            continue  # probable abbreviation (HP, FPS): not judged
        if re.fullmatch(r"[A-Za-z]", word):
            continue  # single stray letter: info-level noise at most
        flags.append(QAFlag("suspicious_latin", "warning",
                            f"untranslated Latin word: {word}", word))
        if len(flags) >= 5:
            break
    return flags


# -- rule C: Arabic presence ---------------------------------------------------------

def _rule_arabic_presence(source: str, translation: str,
                          *, target_is_arabic: bool) -> list[QAFlag]:
    if not target_is_arabic or not translation.strip():
        return []
    if contains_arabic(translation):
        return []
    if _nothing_to_localize(translation):
        return []  # pure game syntax/codes: nothing linguistic to judge
    if re.search(r"[A-Za-z]", translation):
        return [QAFlag("no_arabic_script", "error",
                       "Arabic expected but no Arabic script found",
                       translation[:80])]
    return []


# -- rule D: punctuation -----------------------------------------------------------------

_ARABIC_PUNCT = {"،": ",", "؛": ";", "؟": "?", "…": "...", "：": ":"}
_ENGLISH_PUNCT_RE = re.compile(r"[,.;?!:]")


def _rule_punctuation(source: str, translation: str) -> list[QAFlag]:
    if not contains_arabic(translation):
        return []
    cleaned = _strip_neutral(translation, placeholders=extract_placeholders(translation))
    cleaned = _URL_RE.sub(" ", cleaned)
    cleaned = _VERSION_RE.sub(" ", cleaned)
    cleaned = _DECIMAL_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\d\s*:\s*\d", " ", cleaned)  # times/scores 12:30
    cleaned = re.sub(r"\b[A-Za-z_][\w.]*:", " ", cleaned)  # HP:/UI: labels
    flags: list[QAFlag] = []
    for punct in sorted(set(_ENGLISH_PUNCT_RE.findall(cleaned))):
        arabic_eq = {v: k for k, v in _ARABIC_PUNCT.items()}.get(punct, "")
        hint = f" (consider {arabic_eq})" if arabic_eq else ""
        flags.append(QAFlag("english_punctuation", "warning",
                            f"English '{punct}' in Arabic text{hint}", punct))
    return flags


# -- rule E: placeholders (reuses the existing validator) -----------------------------------

def _rule_placeholders(source: str, translation: str) -> list[QAFlag]:
    report = validate_translation(source, translation)
    flags = [
        QAFlag("placeholder_missing", "error",
               f"lost placeholder: {token}", token)
        for token in report.missing
    ]
    flags.extend(
        QAFlag("placeholder_extra", "warning",
               f"unexpected placeholder: {token}", token)
        for token in report.extra
    )
    return flags


# -- rule F: length -------------------------------------------------------------------------------

def _rule_length(source: str, translation: str,
                 *, max_ratio: float = 1.3, min_ratio: float = 0.4,
                 slack: int = 10) -> list[QAFlag]:
    """Length heuristic with absolute slack for short strings.

    Pure ratios lie on short game lines (``Hi`` → ``مرحبا`` is 3x and
    perfectly fine), so the bound is ``max(ratio, length ± slack)``.
    """
    if not source.strip() or not translation.strip():
        return []
    src_len, tgt_len = len(source), len(translation)
    ratio = tgt_len / src_len
    if tgt_len > max(max_ratio * src_len, src_len + slack):
        return [QAFlag("excessive_length", "warning",
                       f"translation {ratio:.2f}x source length", f"{ratio:.2f}")]
    if tgt_len < min(min_ratio * src_len, src_len - slack):
        return [QAFlag("suspiciously_short", "warning",
                       f"translation {ratio:.2f}x source length", f"{ratio:.2f}")]
    return []


# -- rule G: mixed direction ----------------------------------------------------------------------------

_PAIRS = {"(": ")", "[": "]", "{": "}", "«": "»", "“": "”", "‘": "’"}
_CLOSERS = set(_PAIRS.values())


def _rule_bidi_structure(source: str, translation: str) -> list[QAFlag]:
    """Conservative structural check: unbalanced paired punctuation.

    Full BiDi correctness needs rendering; this flags only mechanically
    unbalanced brackets/quotes, which corrupt display in EITHER direction.
    """
    cleaned = _strip_neutral(translation, placeholders=extract_placeholders(translation))
    flags: list[QAFlag] = []
    for opener, closer in _PAIRS.items():
        if cleaned.count(opener) != cleaned.count(closer):
            flags.append(QAFlag(
                "bidi_unbalanced", "warning",
                f"unbalanced {opener}{closer}: "
                f"{cleaned.count(opener)} opener(s), {cleaned.count(closer)} closer(s)",
                f"{opener}{closer}"))
    return flags


_ARABIC_TARGET_LANGS = frozenset({"ar", "arabic", "ara"})


def _is_arabic_target(target_lang: str) -> bool:
    return (target_lang or "").strip().lower() in _ARABIC_TARGET_LANGS


def arabic_qa_check(
    source_text: str,
    translated_text: str,
    *,
    target_lang: str = "ar",
    entry_id: str | None = None,
    max_length_ratio: float = 1.3,
    min_length_ratio: float = 0.4,
    extra_rules: tuple[QARule, ...] = (),
) -> QAResult:
    """Run the Arabic QA rule set; returns a structured result.

    Rules A–G apply only when the target is Arabic; custom/glossary rules
    always run (they declare their own applicability).
    """
    flags: list[QAFlag] = []
    if _is_arabic_target(target_lang):
        flags.extend(_rule_source_copied(source_text, translated_text))
        flags.extend(_rule_suspicious_latin(source_text, translated_text))
        flags.extend(_rule_arabic_presence(source_text, translated_text,
                                           target_is_arabic=True))
        flags.extend(_rule_punctuation(source_text, translated_text))
        flags.extend(_rule_placeholders(source_text, translated_text))
        flags.extend(_rule_length(source_text, translated_text,
                                  max_ratio=max_length_ratio,
                                  min_ratio=min_length_ratio))
        flags.extend(_rule_bidi_structure(source_text, translated_text))
    for rule in list(CUSTOM_RULES) + list(extra_rules):
        try:
            flags.extend(rule.check(source_text, translated_text,
                                    target_lang=target_lang))
        except Exception as exc:  # a custom rule must never break QA
            flags.append(QAFlag("custom_rule_error", "warning",
                                f"rule {getattr(rule, 'rule_id', '?')} crashed: {exc}",
                                getattr(rule, "rule_id", "?")))
    return QAResult(
        entry_id=entry_id,
        passed=not any(f.severity == "error" for f in flags),
        flags=flags,
    )
