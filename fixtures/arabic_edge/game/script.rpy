# Arabic edge-case fixture for almurrib Phase 2 (deterministic).
# Exercises: pure Arabic, mixed Arabic/Latin, digits, placeholders, markup,
# long sentences, unbreakable tokens, UI text, punctuation, quotes,
# parentheses, menus, and one deliberately untranslated English line.

define e = Character("Eileen")
define s = Character("Sylvie")

label start:
    "مرحبا بالعالم"
    e "Hello مرحبا"
    s "عدد النقاط 125 نقطة"
    e "أهلا {player_name}!"
    s "<color=red>احذر!</color>"
    "صباح الخير"
    e "مساء النور"
    s "تجربة Qwen3 الجديدة"
    e "HP: 100"
    s "هل أنت متأكد؟ (نعم/لا)"
    e "قال: \"مرحبا\"!"
    "This sentence was not translated."
    menu:
        "نعم، أكمل":
            e "اخترت المتابعة."
        "لا، توقف":
            e "توقفت هنا."
    e "هذه جملة عربية طويلة جدا تحتوي على الكثير من الكلمات لاختبار التفاف النص والتأكد من أن المعالجة تتعامل معها بشكل صحيح دون أي مشاكل في الفواصل أو علامات الترقيم."
    e "كلمةطويلةجدابدونأيفراغاتعلىالإطلاقلتختبرالكلماتالمستحيلة"
    return
