"""UI strings resource (English + Arabic) with layout direction.

All widget-visible text lives here — never hard-coded in widget logic.
``t(key)`` falls back to English, then to the key itself, so a missing
translation degrades to readable English instead of crashing.
"""

from __future__ import annotations

UI_LANGS = ("en", "ar")
DIRECTION = {"en": "ltr", "ar": "rtl"}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "game_folder": "Game Folder:",
        "choose_game": "Choose Game Folder…",
        "database": "Database:",
        "browse": "Browse…",
        "output_folder": "Output Folder:",
        "source": "Source:",
        "target": "Target:",
        "provider_config": "Provider Configuration",
        "provider": "Provider:",
        "base_url": "Base URL:",
        "model": "Model:",
        "api_key": "API Key:",
        "test_connection": "Test Connection",
        "refresh_models": "Refresh Models",
        "save_config": "Save Configuration",
        "force_retrans": "Force retranslation (ignore TM/cache/translated)",
        "detect": "Detect",
        "extract": "Extract",
        "translate": "Translate",
        "export": "Export",
        "clear_trans": "Clear Translations",
        "localize_game": "LOCALIZE GAME",
        "unity_one_click": "Unity one-click…",
        "log": "Log",
        "copy_log": "Copy Log",
        "clear_log": "Clear Log",
        "copy": "Copy",
        "copy_all": "Copy All",
        "select_all": "Select All",
        "ui_language": "عربي",
        "pick_game_title": "Choose game folder",
        "pick_db_title": "Database",
        "pick_out_title": "Output Folder",
        "already_running": "An operation is already running.",
        "confirm_clear_title": "Clear translations?",
        "confirm_clear_body": ("Clear all stored translations for this game?\n\n"
                               "Source entries stay; obsolete history is preserved.\n"
                               "Next Translate will call the provider fresh."),
        "config_saved": "configuration saved to {path}",
        "config_where": "config: {path}",
        "entries_extracted": "{count} entries extracted",
        "detecting": "Detecting engine...",
        "extracting": "Extracting text...",
        "translating": "Translating...",
        "exporting": "Exporting localization...",
        "localizing": "Running full localization...",
        "clearing": "Clearing translations...",
        "testing": "Testing connection...",
        "refreshing": "Refreshing models...",
        "no_project": "no stored project for this game — run Extract first",
        "no_entries": "no entries stored — run Extract first",
        "nothing_to_clear": "no stored project for this game — nothing to clear",
        "log_copied": "log copied to clipboard (secrets redacted)",
        "save_failed": "could not save configuration: {error}",
        "models_source": "Models source: ● {source}",
        "source_live": "Live provider API",
        "source_models_dev": "Models.dev",
        "source_litellm": "LiteLLM catalog",
        "source_static": "Static fallback",
        "source_local": "Local models",
        "exported": "exported {count} file(s): {files}",
        "localize_done": ("{extracted} extracted; {translated} translated via API; "
                          "{count} file(s) exported to {out}"),
        "detected": "{engine} detected (confidence {confidence})",
        "simple_mode": "Simple",
        "advanced_mode": "Advanced",
        "start": "START",
        "game": "Game",
        "language": "Language",
        "api_key_optional": "API Key (optional for local/offline)",
        "detect_info": "Detected engine: {engine}",
        "detect_none": "No supported engine detected — see Advanced.",
        "phase": "Phase: {phase}",
        "summary_line": "Done: {summary}",
        "status_ready": "Ready. Pick a game folder, then press START.",
        "cap_extract": "Extract",
        "cap_build": "Build",
        "cap_runtime": "Runtime",
        "cap_unsupported": "unsupported",
    },
    "ar": {
        "game_folder": "مجلد اللعبة:",
        "choose_game": "اختيار مجلد اللعبة…",
        "database": "قاعدة البيانات:",
        "browse": "تصفح…",
        "output_folder": "مجلد المخرجات:",
        "source": "المصدر:",
        "target": "الهدف:",
        "provider_config": "إعدادات المزود",
        "provider": "المزود:",
        "base_url": "الرابط:",
        "model": "النموذج:",
        "api_key": "مفتاح API:",
        "test_connection": "اختبار الاتصال",
        "refresh_models": "تحديث النماذج",
        "save_config": "حفظ الإعدادات",
        "force_retrans": "إعادة ترجمة إجبارية (تجاهل الذاكرة والكاش والمترجم)",
        "detect": "كشف",
        "extract": "استخراج",
        "translate": "ترجمة",
        "export": "تصدير",
        "clear_trans": "مسح الترجمات",
        "localize_game": "تعريب اللعبة",
        "unity_one_click": "تعريب Unity بضغطة…",
        "log": "السجل",
        "copy_log": "نسخ السجل",
        "clear_log": "مسح السجل",
        "copy": "نسخ",
        "copy_all": "نسخ الكل",
        "select_all": "تحديد الكل",
        "ui_language": "EN",
        "pick_game_title": "اختيار مجلد اللعبة",
        "pick_db_title": "قاعدة البيانات",
        "pick_out_title": "مجلد المخرجات",
        "already_running": "هناك عملية جارية بالفعل.",
        "confirm_clear_title": "مسح الترجمات؟",
        "confirm_clear_body": ("مسح كل الترجمات المخزنة لهذه اللعبة؟\n\n"
                               "سطور المصدر تبقى، والسجل القديم محفوظ.\n"
                               "الترجمة التالية ستستدعي المزود من جديد."),
        "config_saved": "تم حفظ الإعدادات في {path}",
        "config_where": "الإعدادات: {path}",
        "entries_extracted": "تم استخراج {count} سطرًا",
        "detecting": "جارٍ كشف المحرك…",
        "extracting": "جارٍ استخراج النصوص…",
        "translating": "جارٍ الترجمة…",
        "exporting": "جارٍ تصدير التعريب…",
        "localizing": "جارٍ التعريب الكامل…",
        "clearing": "جارٍ مسح الترجمات…",
        "testing": "جارٍ اختبار الاتصال…",
        "refreshing": "جارٍ تحديث النماذج…",
        "no_project": "لا مشروع مخزن لهذه اللعبة — نفّذ الاستخراج أولًا",
        "no_entries": "لا سطور مخزنة — نفّذ الاستخراج أولًا",
        "nothing_to_clear": "لا مشروع مخزن لهذه اللعبة — لا شيء لمسحه",
        "log_copied": "تم نسخ السجل (أُخفيت الأسرار)",
        "save_failed": "تعذر حفظ الإعدادات: {error}",
        "models_source": "مصدر النماذج: ● {source}",
        "source_live": "واجهة المزود الحية",
        "source_models_dev": "Models.dev",
        "source_litellm": "كتالوج LiteLLM",
        "source_static": "احتياطي ثابت",
        "source_local": "نماذج محلية",
        "exported": "تم تصدير {count} ملف: {files}",
        "localize_done": ("تم استخراج {extracted}؛ تُرجم {translated} عبر API؛ "
                          "صُدّر {count} ملف إلى {out}"),
        "detected": "تم الكشف: {engine} (الثقة {confidence})",
        "simple_mode": "بسيط",
        "advanced_mode": "متقدم",
        "start": "ابدأ",
        "game": "اللعبة",
        "language": "اللغة",
        "api_key_optional": "مفتاح API (اختياري للمحلي)",
        "detect_info": "المحرك المكتشف: {engine}",
        "detect_none": "لم يُكتشف محرك مدعوم — انظر المتقدم.",
        "phase": "المرحلة: {phase}",
        "summary_line": "انتهى: {summary}",
        "status_ready": "جاهز. اختر مجلد اللعبة ثم اضغط ابدأ.",
        "cap_extract": "استخراج",
        "cap_build": "بناء",
        "cap_runtime": "تشغيل",
        "cap_unsupported": "غير مدعوم",
    },
}


def t(key: str, lang: str = "en", **values: object) -> str:
    """Look up a UI string (English fallback, then the key itself)."""
    template = STRINGS.get(lang, {}).get(key) or STRINGS["en"].get(key) or key
    if values:
        try:
            return template.format(**values)
        except (KeyError, IndexError, ValueError):
            return template
    return template


def direction(lang: str) -> str:
    """Layout direction for a UI language ('ltr' default)."""
    return DIRECTION.get(lang, "ltr")
