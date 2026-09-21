"""Ren'Py .rpy source parser (extraction-oriented, conservative).

This is NOT a full Ren'Py grammar. It deliberately extracts only
*unambiguous translatable text* from script source, in a deterministic way:

* character say statements:   ``e "Hello."``
* narrator say statements:    ``"The wind blows."``
* menu choices:               ``"Yes, I do":``
* ``translate <lang> strings:`` old/new pairs (existing translations —
  extracted as reference, tagged so the pipeline can skip re-translating)

Skipped on purpose (recorded as notes, not text): comments, ``# TODO``,
python blocks, labels/jumps, image/scene/show statements, screen language,
interpolation-only expressions. Compiled ``.rpyc`` decompilation is out of
scope for this half of Phase 1.

Output is a list of :class:`RawStatement` — the adapter layer converts
these into the normalized model.
"""

from __future__ import annotations

import re
from pathlib import Path

from almurrib.core.errors import ExtractionError
from almurrib.engine_adapters.raw import RawStatement

# Quoted-string body that understands backslash escapes: an escaped pair
# (\" \\ \n ...) never terminates the string. Extracted text is then fully
# unescaped so entries hold RUNTIME values (what Ren'Py matches at display
# time) instead of source-literal backslashes.
_ESCAPED_BODY = r"(?P<text>(?:\\.|(?!(?P=quote)).)*)"

# Character definition: define e = Character("Eileen")
# Also handles translatable display names: define s = Character(_("Sylvie"), ...)
DEFINE_CHARACTER_RE = re.compile(
    r"""^\s*define\s+(?P<var>[A-Za-z_]\w*)\s*=\s*Character\(\s*(?P<marked>_\(\s*)?(?P<quote>["'])"""
    + _ESCAPED_BODY.replace("(?P<text>", "(?P<name>", 1) +
    r"""(?P=quote)"""
)

# Say statement with a speaker: e "Hello."  /  e 'Hello.'
SAY_WITH_SPEAKER_RE = re.compile(
    r"""^\s*(?P<speaker>[A-Za-z_]\w*)\s+(?P<quote>["'])"""
    + _ESCAPED_BODY +
    r"""(?P=quote)\s*(?:#.*)?$"""
)

# Narrator say statement: "The wind blows."
SAY_NARRATOR_RE = re.compile(
    r"""^\s*(?P<quote>["'])""" + _ESCAPED_BODY + r"""(?P=quote)\s*(?:#.*)?$"""
)

# Menu choice: "Yes, I do":   (only when we are inside a menu block)
MENU_CHOICE_RE = re.compile(
    r"""^\s*(?P<quote>["'])""" + _ESCAPED_BODY + r"""(?P=quote)\s*:\s*(?:#.*)?$"""
)

MENU_RE = re.compile(r"^\s*menu\s*(?:[A-Za-z_]\w*)?\s*:\s*(?:#.*)?$")
TRANSLATE_STRINGS_RE = re.compile(r"^\s*translate\s+\w+\s+strings\s*:\s*(?:#.*)?$")
OLD_RE = re.compile(
    r"""^\s*old\s+(?P<quote>["'])""" + _ESCAPED_BODY + r"""(?P=quote)\s*(?:#.*)?$""")
NEW_RE = re.compile(
    r"""^\s*new\s+(?P<quote>["'])""" + _ESCAPED_BODY + r"""(?P=quote)\s*(?:#.*)?$""")


_SIMPLE_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'",
}
_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})|\\U([0-9a-fA-F]{8})")


def unescape_renpy_string(raw: str) -> str:
    """Resolve Ren'Py string escapes to runtime values.

    ``\\"`` → ``"``, ``\\n`` → newline, ``\\uXXXX`` → char. Unknown escapes
    keep their backslash (never silently drop content).
    """
    def replace_unicode(match: re.Match[str]) -> str:
        code = match.group(1) or match.group(2)
        try:
            return chr(int(code, 16))
        except (ValueError, OverflowError):
            return match.group(0)

    text = _UNICODE_ESCAPE_RE.sub(replace_unicode, raw)
    out: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            out.append(_SIMPLE_ESCAPES.get(nxt, "\\" + nxt))
            i += 2
        else:
            out.append(char)
            i += 1
    return "".join(out)

# Lines that look like code or statements we intentionally ignore, so we
# don't mistake their string literals for translatable dialogue.
IGNORED_PREFIXES = (
    "$", "python", "init", "define", "default", "label", "jump", "call",
    "return", "scene", "show", "hide", "image", "play", "stop", "queue",
    "voice", "sound", "music", "screen", "transform", "style", "if",
    "elif", "else", "while", "for", "pass", "with", "pause", "window",
    "nvl", "translate", "old", "new",
)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def parse_rpy(path: Path, *, game_root: Path) -> list[RawStatement]:
    """Parse a single .rpy file into raw statements."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ExtractionError(
            f"could not read Ren'Py script '{path}': {exc}",
            hint="scripts must be readable UTF-8 text.",
        ) from exc

    rel = path.relative_to(game_root).as_posix()
    lines = text.splitlines()

    characters: dict[str, str] = {}  # variable -> display name
    statements: list[RawStatement] = []

    in_menu = False
    menu_indent = 0
    in_translate_strings = False
    translate_indent = 0
    pending_old: tuple[str, int] | None = None  # (text, line)

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip()
        stripped = line.strip()
        indent = _indent(raw)

        # Comments and blank lines never produce statements, but they do
        # NOT close enclosing blocks (Ren'Py allows them anywhere).
        if not stripped or stripped.startswith("#"):
            continue

        if in_menu and indent <= menu_indent and not stripped.startswith(('"', "'")):
            in_menu = False
        if in_translate_strings and indent <= translate_indent and not stripped.startswith(
            ("old ", "new ", 'old"', 'new"', "old'", "new'")
        ):
            in_translate_strings = False
            pending_old = None

        # --- character definitions --------------------------------------
        m = DEFINE_CHARACTER_RE.match(line)
        if m:
            name = unescape_renpy_string(m.group("name"))
            characters[m.group("var")] = name
            if m.group("marked"):
                # _(...) explicitly marks the display name translatable:
                # the nameplate itself becomes a localization entry.
                statements.append(
                    RawStatement(
                        kind="character_name",
                        text=name,
                        file=rel,
                        line=lineno,
                        speaker_var=m.group("var"),
                    )
                )
            continue

        # --- translate <lang> strings blocks ----------------------------
        if TRANSLATE_STRINGS_RE.match(line):
            in_translate_strings = True
            translate_indent = indent
            pending_old = None
            continue
        if in_translate_strings:
            m = OLD_RE.match(line)
            if m:
                pending_old = (unescape_renpy_string(m.group("text")), lineno)
                continue
            m = NEW_RE.match(line)
            if m and pending_old is not None:
                statements.append(
                    RawStatement(
                        kind="translated_string",
                        text=pending_old[0],
                        translation=unescape_renpy_string(m.group("text")),
                        file=rel,
                        line=pending_old[1],
                        extra={"new_line": str(lineno)},
                    )
                )
                pending_old = None
                continue
            continue  # ignore anything else inside translate blocks

        # --- menus -------------------------------------------------------
        if MENU_RE.match(line):
            in_menu = True
            menu_indent = indent
            continue
        if in_menu:
            m = MENU_CHOICE_RE.match(line)
            if m:
                statements.append(
                    RawStatement(kind="menu_choice",
                                 text=unescape_renpy_string(m.group("text")),
                                 file=rel, line=lineno)
                )
                continue

        # --- statements we deliberately ignore ---------------------------
        head = stripped.split(None, 1)[0] if stripped else ""
        if stripped.startswith(IGNORED_PREFIXES) or head in IGNORED_PREFIXES:
            continue

        # --- say statements ----------------------------------------------
        m = SAY_WITH_SPEAKER_RE.match(line)
        if m:
            var = m.group("speaker")
            statements.append(
                RawStatement(
                    kind="say",
                    text=unescape_renpy_string(m.group("text")),
                    file=rel,
                    line=lineno,
                    speaker=characters.get(var, var),
                    speaker_var=var,
                )
            )
            continue
        m = SAY_NARRATOR_RE.match(line)
        if m:
            statements.append(
                RawStatement(kind="say",
                             text=unescape_renpy_string(m.group("text")),
                             file=rel, line=lineno, speaker=None)
            )
            continue

    return statements

