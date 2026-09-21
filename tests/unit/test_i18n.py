"""i18n resource + RTL direction tests (headless-safe, no Tk needed)."""

from almurrib.gui.i18n import DIRECTION, STRINGS, UI_LANGS, direction, t


def test_both_languages_present():
    assert set(UI_LANGS) == {"en", "ar"}
    assert set(STRINGS.keys()) == {"en", "ar"}


def test_key_parity_no_empties():
    en_keys, ar_keys = set(STRINGS["en"]), set(STRINGS["ar"])
    assert en_keys == ar_keys, f"missing: {en_keys ^ ar_keys}"
    for lang in UI_LANGS:
        for key, value in STRINGS[lang].items():
            assert value.strip(), (lang, key)


def test_lookup_and_format():
    assert t("detect", "en") == "Detect"
    assert t("detect", "ar") == "كشف"
    assert t("entries_extracted", "ar", count=5) == "تم استخراج 5 سطرًا"
    assert t("entries_extracted", "en", count=5) == "5 entries extracted"


def test_fallback_english_then_key():
    assert t("detect", "fr") == "Detect"  # unknown lang -> English
    assert t("missing_key_xyz", "ar") == "missing_key_xyz"


def test_direction_mapping():
    assert direction("en") == "ltr"
    assert direction("ar") == "rtl"
    assert direction("xx") == "ltr"
    assert set(DIRECTION.values()) == {"ltr", "rtl"}
