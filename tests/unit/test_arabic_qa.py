"""Arabic QA engine tests: rules A-G, severities, extensibility."""

from almurrib.arabic.qa import (
    CUSTOM_RULES,
    QAFlag,
    arabic_qa_check,
    register_qa_rule,
)


def _ids(result):
    return [(f.rule_id, f.severity) for f in result.flags]


# -- A: source copied -------------------------------------------------------------

def test_source_copied_is_error():
    result = arabic_qa_check("Hello world", "Hello world")
    assert ("source_copied", "error") in _ids(result)
    assert not result.passed


def test_source_copied_ignores_digits_only():
    assert arabic_qa_check("123", "123").passed


def test_source_copied_ignores_placeholder_only():
    assert arabic_qa_check("[score]", "[score]").passed


def test_abbreviation_codes_exempt_but_single_letters_flagged():
    assert arabic_qa_check("HP: 100", "HP: 100").passed
    assert arabic_qa_check("HP", "HP").passed
    flagged = arabic_qa_check("A", "A")
    assert any(f.rule_id == "source_copied" for f in flagged.flags)


def test_different_text_no_copy_flag():
    assert all(f.rule_id != "source_copied"
               for f in arabic_qa_check("Hello", "مرحبا").flags)


# -- B: suspicious Latin ---------------------------------------------------------------

def test_latin_allowlist_and_abbreviations_pass():
    result = arabic_qa_check("x", "نموذج Qwen3 سريع HP عالي")
    assert all(f.rule_id != "suspicious_latin" for f in result.flags)


def test_untranslated_latin_word_warns():
    result = arabic_qa_check("Welcome", "مرحبا Welcome يا صديقي")
    hits = [f for f in result.flags if f.rule_id == "suspicious_latin"]
    assert hits and hits[0].severity == "warning"
    assert "Welcome" in hits[0].evidence


def test_urls_emails_versions_exempt():
    result = arabic_qa_check(
        "x", "زر الموقع https://example.com يا user@mail.com إصدار 2.5")
    assert all(f.rule_id != "suspicious_latin" for f in result.flags)


# -- C: Arabic presence -------------------------------------------------------------------

def test_no_arabic_script_is_error():
    result = arabic_qa_check("Hello", "Hello!")
    assert ("no_arabic_script", "error") in _ids(result)


def test_arabic_present_passes():
    assert all(f.rule_id != "no_arabic_script"
               for f in arabic_qa_check("Hello", "مرحبا!").flags)


def test_non_arabic_target_skips_core_rules():
    result = arabic_qa_check("Hello", "Hello!", target_lang="fr")
    assert result.passed and result.flags == []


# -- D: punctuation -------------------------------------------------------------------------------

def test_english_comma_warns_with_arabic_hint():
    result = arabic_qa_check("x", "مرحبا, يا صديقي")
    hits = [f for f in result.flags if f.rule_id == "english_punctuation"]
    assert hits and "،" in hits[0].message


def test_arabic_punctuation_passes():
    result = arabic_qa_check("x", "مرحبا، يا صديقي؟")
    assert all(f.rule_id != "english_punctuation" for f in result.flags)


def test_decimals_times_labels_exempt():
    result = arabic_qa_check("x", "السعر 3.14 والنتيجة 12:30 يا HP: قوي")
    assert all(f.rule_id != "english_punctuation" for f in result.flags)


# -- E: placeholders -------------------------------------------------------------------------------------

def test_placeholder_missing_error_extra_warning():
    result = arabic_qa_check("Hi {name} %s", "مرحبا %s %d")
    kinds = {f.rule_id: f.severity for f in result.flags}
    assert kinds.get("placeholder_missing") == "error"
    assert kinds.get("placeholder_extra") == "warning"
    missing = [f for f in result.flags if f.rule_id == "placeholder_missing"]
    assert [f.evidence for f in missing] == ["{name}"]
    # All preserved: no missing flag, extra still reported.
    clean = arabic_qa_check("Hi {name} %s", "مرحبا {name} %s")
    assert all(f.rule_id != "placeholder_missing" for f in clean.flags)


def test_storage_token_format():
    result = arabic_qa_check("Hi {name}", "مرحبا")
    (flag,) = [f for f in result.flags if f.rule_id == "placeholder_missing"]
    assert flag.storage_token() == "placeholder_missing:{name}"


# -- F: length ------------------------------------------------------------------------------------------------

def test_excessive_length_warns():
    result = arabic_qa_check("Hi", "مرحبا بك يا صديقي العزيز جدا")
    assert any(f.rule_id == "excessive_length" and f.severity == "warning"
               for f in result.flags)


def test_suspiciously_short_warns():
    result = arabic_qa_check(
        "This is a fairly long source sentence here", "نعم")
    assert any(f.rule_id == "suspiciously_short" for f in result.flags)


def test_normal_ratio_passes():
    assert all(f.rule_id not in ("excessive_length", "suspiciously_short")
               for f in arabic_qa_check("Hello world", "مرحبا بالعالم").flags)


def test_short_lines_get_absolute_slack():
    """Hi → مرحبا is 3x and perfectly fine; pure ratios lie on short text."""
    result = arabic_qa_check("Hi", "مرحبا")
    assert all(f.rule_id not in ("excessive_length", "suspiciously_short")
               for f in result.flags)
    assert all(f.rule_id not in ("excessive_length", "suspiciously_short")
               for f in arabic_qa_check("Yes", "نعم").flags)


def test_custom_ratios():
    result = arabic_qa_check("Hi", "مرحبا بك", max_length_ratio=99.0)
    assert all(f.rule_id != "excessive_length" for f in result.flags)


# -- G: bidi structure ------------------------------------------------------------------------------------

def test_unbalanced_parens_warn():
    result = arabic_qa_check("x", "قال (مرحبا يا صديقي")
    assert any(f.rule_id == "bidi_unbalanced" for f in result.flags)


def test_balanced_passes():
    assert all(f.rule_id != "bidi_unbalanced"
               for f in arabic_qa_check("x", "قال (مرحبا)").flags)


# -- H: extensibility ----------------------------------------------------------------------------------------

def test_custom_rule_hook_and_crash_isolation():
    before = len(CUSTOM_RULES)

    class Noisy:
        rule_id = "noisy"

        def check(self, source, translation, *, target_lang):
            return [QAFlag("noisy", "info", "always", "")]

    class Broken:
        rule_id = "broken"

        def check(self, source, translation, *, target_lang):
            raise RuntimeError("boom")

    register_qa_rule(Noisy())
    register_qa_rule(Broken())
    try:
        result = arabic_qa_check("Hello", "مرحبا")
        assert any(f.rule_id == "noisy" for f in result.flags)
        crashed = [f for f in result.flags if f.rule_id == "custom_rule_error"]
        assert crashed and crashed[0].severity == "warning"
        assert result.passed  # custom crashes never fail QA
    finally:
        del CUSTOM_RULES[before:]


def test_bad_severity_rejected():
    import pytest

    with pytest.raises(ValueError):
        QAFlag("x", "critical", "m")
