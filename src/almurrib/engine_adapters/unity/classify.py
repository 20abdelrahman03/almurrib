"""String candidate classification (§10 of the Unity milestone).

Not every string in a Unity game is dialogue. This module classifies each
candidate as LIKELY / POSSIBLY translatable or TECHNICAL (leave unchanged)
with an explainable reason. Classification is advisory: extraction keeps
everything, the verdict travels as entry tags/metadata so translation,
QA and failure diagnostics can show *why* a string was (skipped).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Verdict(str, Enum):
    LIKELY = "likely"
    POSSIBLY = "possibly"
    TECHNICAL = "technical"


@dataclass(frozen=True)
class Classification:
    verdict: Verdict
    reason: str


_GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_URL_RE = re.compile(r"^(https?://|www\.)", re.IGNORECASE)
_PATH_RE = re.compile(r"^(Assets/|Packages/|Library/|[A-Za-z]:[\\/]|/)")
_EXT_RE = re.compile(r"\.(dll|exe|shader|mat|prefab|cs|js|json|xml|png|jpg|"
                     r"wav|mp3|ogg|fbx|anim|controller|asset|bundle|ab)$",
                     re.IGNORECASE)
_ID_RE = re.compile(r"^#?\d+$")
# ALL-CAPS prefix + separator + digits (QUEST_042) or a short alpha
# prefix glued to digits (L12). Mixed-case words with spaces ("Chapter 2")
# are chapter titles, not IDs — they must NOT match.
_PREFixed_ID_RE = re.compile(r"^(?:[A-Z][A-Z0-9]*[-_#]\d+|[A-Za-z]{1,4}\d{2,})$")
_DEBUG_RE = re.compile(r"(^_|__)")
_NAMESPACE_RE = re.compile(r"^[A-Za-z_][\w]*(\.[\w]+)+$")


def classify_candidate(text: str, *, field_path: str = "",
                       object_name: str = "",
                       class_name: str = "") -> Classification:
    """Classify one string candidate. Pure function, stdlib only."""
    stripped = text.strip()
    if not stripped:
        return Classification(Verdict.TECHNICAL, "empty/whitespace")

    lowered = stripped.lower()
    if _GUID_RE.match(stripped):
        return Classification(Verdict.TECHNICAL, "GUID")
    if _URL_RE.match(stripped):
        return Classification(Verdict.TECHNICAL, "URL")
    if _PATH_RE.match(stripped) or (
            ("\\" in stripped or "/" in stripped)
            and _EXT_RE.search(stripped)):
        return Classification(Verdict.TECHNICAL, "file path")
    if lowered.endswith((".dll", ".exe")):
        return Classification(Verdict.TECHNICAL, "assembly/binary name")
    if lowered.endswith(".shader") or "shader" in field_path.lower():
        return Classification(Verdict.TECHNICAL, "shader name")
    if _ID_RE.match(stripped):
        return Classification(Verdict.TECHNICAL, "numeric ID")
    if _PREFixed_ID_RE.match(stripped.replace(" ", "")):
        return Classification(Verdict.TECHNICAL, "internal ID")
    if _DEBUG_RE.search(stripped) and " " not in stripped:
        return Classification(Verdict.TECHNICAL, "debug identifier")
    if _NAMESPACE_RE.match(stripped):
        return Classification(Verdict.TECHNICAL, "dotted class/name")

    # Single-token identifiers: could be an item name (translate!) or a
    # key (don't). Human call — POSSIBLY, never silent.
    if " " not in stripped and ("\n" not in stripped) and (
            "_" in stripped or "." in stripped
            or (any(c.isdigit() for c in stripped)
                and any(c.isalpha() for c in stripped))):
        return Classification(Verdict.POSSIBLY,
                              "identifier-shaped token (key or name?)")

    # Very short UI fragments without sentence structure: possibly a
    # label (translate) or a code ("OK"/"ID"/"v2") — POSSIBLY.
    if len(stripped) <= 2:
        return Classification(Verdict.POSSIBLY, "tiny fragment")

    return Classification(Verdict.LIKELY, "prose-shaped text")
