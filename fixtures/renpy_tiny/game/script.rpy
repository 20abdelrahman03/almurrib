# Tiny Ren'Py fixture for almurrib tests.
# Deterministic: fixed lines, fixed content.

define e = Character("Eileen")
define n = Character("Nadia")

label start:
    "The wind blows over the empty street."
    e "Hello! Did you wait long?"
    n "Not at all. I just arrived."
    e "Let's go inside."
    jump choice_scene

label choice_scene:
    menu:
        "Follow Eileen":
            n "I follow her quietly."
        "Stay outside":
            n "I need a moment alone."

    e "This is the end of the fixture."
    return
