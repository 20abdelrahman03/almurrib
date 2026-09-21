"""Character/terminology glossary: deterministic, provider-independent.

A glossary binds source terms to approved Arabic translations with optional
character metadata (gender, speech style). It feeds translation three ways:

1. **Context to providers** — matched pairs travel inside the generic
   prompt (``TranslationRequest.glossary``); no provider-specific code.
2. **QA enforcement** — mismatches become structured ``glossary.*`` flags
   (characters: error, terms: warning, forbidden variants: error).
3. **TM/cache safety** — translations produced under a glossary carry a
   glossary revision in the cache identity, so edited glossaries cannot
   silently serve stale cached text.

Matching is deterministic (longest match, case-insensitive, word-boundary
aware) and never rewrites translations by substring replacement — the model
receives guidance; QA verifies the result.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from almurrib.core.model import LocalizationEntry

GLOBAL_PROJECT_ID = 0  # project_id 0 = shared/global entries

VALID_TYPES = ("character", "term")
VALID_GENDERS = ("female", "male", "neutral", "unknown")
VALID_STYLES = ("formal", "standard", "colloquial", "rough", "polite",
                "childlike", "technical", "unspecified")


@dataclass(frozen=True)
class GlossaryEntry:
    """One approved terminology binding."""

    source_term: str
    target_term: str
    type: str = "term"  # "character" | "term"
    gender: str | None = None  # characters: female | male | neutral | unknown
    style: str | None = None  # formal | standard | colloquial | ...
    pronunciation: str | None = None
    notes: str | None = None
    aliases: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()  # variants that must NOT appear
    enabled: bool = True
    project_id: int = GLOBAL_PROJECT_ID
    id: int | None = None  # None until persisted

    def __post_init__(self) -> None:
        if not self.source_term or not self.source_term.strip():
            raise ValueError("source_term must not be empty")
        if not self.target_term or not self.target_term.strip():
            raise ValueError("target_term must not be empty")
        if self.type not in VALID_TYPES:
            raise ValueError(f"bad type: {self.type!r}")
        if self.gender is not None and self.gender not in VALID_GENDERS:
            raise ValueError(f"bad gender: {self.gender!r}")
        if self.style is not None and self.style not in VALID_STYLES:
            raise ValueError(f"bad style: {self.style!r}")

    def to_dict(self) -> dict:
        return {
            "source_term": self.source_term,
            "target_term": self.target_term,
            "type": self.type,
            "gender": self.gender,
            "style": self.style,
            "pronunciation": self.pronunciation,
            "notes": self.notes,
            "aliases": list(self.aliases),
            "forbidden": list(self.forbidden),
            "enabled": self.enabled,
            "project_id": self.project_id,
        }

    @staticmethod
    def from_dict(data: dict) -> "GlossaryEntry":
        return GlossaryEntry(
            source_term=str(data["source_term"]),
            target_term=str(data["target_term"]),
            type=str(data.get("type", "term")),
            gender=data.get("gender"),
            style=data.get("style"),
            pronunciation=data.get("pronunciation"),
            notes=data.get("notes"),
            aliases=tuple(data.get("aliases") or ()),
            forbidden=tuple(data.get("forbidden") or ()),
            enabled=bool(data.get("enabled", True)),
            project_id=int(data.get("project_id", GLOBAL_PROJECT_ID)),
        )


@dataclass(frozen=True)
class GlossaryMatch:
    """One glossary hit inside a source text (surface form preserved)."""

    entry: GlossaryEntry
    matched_text: str


@dataclass(frozen=True)
class TranslationContext:
    """Everything the provider may use beyond the raw source text."""

    speaker: str | None = None
    speaker_gender: str | None = None
    speaker_style: str | None = None
    glossary_matches: tuple[GlossaryMatch, ...] = ()
    nearby_context: str | None = None

    @property
    def glossary_terms(self) -> tuple[tuple[str, str], ...]:
        """Deterministic (source, target) pairs for the prompt."""
        seen: dict[str, str] = {}
        for match in self.glossary_matches:
            seen.setdefault(match.entry.source_term, match.entry.target_term)
        return tuple(sorted(seen.items()))


from functools import lru_cache


@lru_cache(maxsize=4096)
def _boundary_pattern(term: str) -> "re.Pattern[str]":
    # Word-boundary aware, case-insensitive: "Me" must not match "memory".
    # Cached: compiling per lookup dominates at 10k-entry scale.
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)


@dataclass
class Glossary:
    """In-memory terminology collection with deterministic lookup."""

    entries: list[GlossaryEntry] = field(default_factory=list)

    def enabled(self) -> list[GlossaryEntry]:
        return [e for e in self.entries if e.enabled]

    def lookup(self, text: str) -> list[GlossaryMatch]:
        """All matches, longest-first, non-overlapping (deterministic)."""
        candidates = sorted(self.enabled(), key=lambda e: len(e.source_term),
                            reverse=True)
        lowered = text.casefold()  # one pass; substring prefilter below
        claimed: list[tuple[int, int]] = []
        matches: list[GlossaryMatch] = []
        for entry in candidates:
            surfaces = [entry.source_term, *entry.aliases]
            for surface in surfaces:
                if not surface.strip():
                    continue
                # Cheap necessary condition: no substring, no regex needed.
                if surface.casefold() not in lowered:
                    continue
                for match in _boundary_pattern(surface).finditer(text):
                    start, end = match.span()
                    if any(start < c_end and end > c_start
                           for c_start, c_end in claimed):
                        continue
                    claimed.append((start, end))
                    matches.append(GlossaryMatch(entry, match.group(0)))
        matches.sort(key=lambda m: text.find(m.matched_text))
        return matches

    def character_for(self, speaker: str | None) -> GlossaryEntry | None:
        """Character entry whose term/alias equals the speaker name."""
        if not speaker:
            return None
        wanted = speaker.strip().casefold()
        for entry in self.enabled():
            if entry.type != "character":
                continue
            names = [entry.source_term, *entry.aliases]
            if any(n.strip().casefold() == wanted for n in names if n.strip()):
                return entry
        return None

    def revision(self) -> str:
        """Short deterministic hash of the enabled set (cache scoping)."""
        digest = hashlib.sha256()
        for entry in sorted(self.enabled(), key=lambda e: e.source_term.lower()):
            digest.update(b"\x1f")
            digest.update(entry.source_term.lower().encode("utf-8"))
            digest.update(b"\x1f")
            digest.update(entry.target_term.encode("utf-8"))
        return digest.hexdigest()[:12]

    def __len__(self) -> int:
        return len(self.entries)


def build_translation_context(
    entry: LocalizationEntry, glossary: Glossary | None
) -> TranslationContext:
    """Assemble provider context: speaker metadata + glossary matches."""
    if glossary is None:
        return TranslationContext(speaker=entry.speaker,
                                  nearby_context=entry.context)
    character = glossary.character_for(entry.speaker)
    return TranslationContext(
        speaker=entry.speaker,
        speaker_gender=character.gender if character else None,
        speaker_style=character.style if character else None,
        glossary_matches=tuple(glossary.lookup(entry.source_text)),
        nearby_context=entry.context,
    )


def _compare_form(text: str) -> str:
    """Orthographic normalization for COMPARISON ONLY (never stored).

    Collapses alef variants, ta-marbuta/ya quirks, tashkeel and tatweel so
    valid inflected/rendered forms are not flagged as mismatches.
    """
    out = text
    for variant in ("أ", "إ", "آ", "ٱ"):
        out = out.replace(variant, "ا")
    out = out.replace("ة", "ه").replace("ى", "ي")
    out = "".join(c for c in out if not ("\u064b" <= c <= "\u0652"))
    return out.replace("ـ", "").casefold()


def glossary_qa_check(
    source_text: str,
    translated_text: str,
    matches: list[GlossaryMatch],
) -> list:
    """Verify glossary terms survived translation (structured flags).

    Characters mismatch → error; terms → warning; forbidden variants →
    error. Comparison uses orthographic normalization so valid Arabic
    forms are never flagged for byte-inequality with the glossary target.
    """
    from almurrib.arabic.qa import QAFlag

    flags: list = []
    norm_translated = _compare_form(translated_text)
    for match in matches:
        entry = match.entry
        expected = _compare_form(entry.target_term)
        if expected and expected not in norm_translated:
            severity = "error" if entry.type == "character" else "warning"
            flags.append(QAFlag(
                "glossary.mismatch", severity,
                f"expected '{entry.target_term}' for '{match.matched_text}'",
                translated_text[:80],
            ))
        for forbidden in entry.forbidden:
            if forbidden and _compare_form(forbidden) in norm_translated:
                flags.append(QAFlag(
                    "glossary.forbidden", "error",
                    f"forbidden variant '{forbidden}' present",
                    forbidden,
                ))
    return flags


def merge_glossaries(*glossaries: Glossary) -> Glossary:
    """Project entries win over global ones (case-insensitive source term).

    An explicitly disabled entry in a higher-priority glossary suppresses
    the same term from lower-priority ones (disable means off, not absent).
    """
    seen: set[str] = set()
    suppressed: set[str] = set()
    merged: list[GlossaryEntry] = []
    disabled: list[GlossaryEntry] = []
    for glossary in glossaries:
        for entry in glossary.entries:
            key = entry.source_term.casefold()
            if not entry.enabled:
                if key not in seen:
                    suppressed.add(key)
                    disabled.append(entry)
                continue
            if key in seen or key in suppressed:
                continue
            seen.add(key)
            merged.append(entry)
    out = Glossary()
    out.entries.extend(merged)
    out.entries.extend(disabled)
    return out


GLOSSARY_FORMAT = "almurrib-glossary"
GLOSSARY_FORMAT_VERSION = 1
_CSV_COLUMNS = ("source_term", "target_term", "type", "gender", "style",
                "pronunciation", "notes", "aliases", "forbidden", "enabled")


def export_json(glossary: Glossary) -> str:
    """Human-editable JSON export (project scope preserved per entry)."""
    import json

    payload = {
        "format": GLOSSARY_FORMAT,
        "format_version": GLOSSARY_FORMAT_VERSION,
        "entry_count": len(glossary.entries),
        "entries": [e.to_dict() for e in glossary.entries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2,
                      sort_keys=True) + "\n"


def _split_list(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(part.strip() for part in str(value).split("|") if part.strip())


def export_csv(glossary: Glossary) -> str:
    """Human-editable CSV export (lists joined with ``|``)."""
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(_CSV_COLUMNS))
    writer.writeheader()
    for entry in glossary.entries:
        data = entry.to_dict()
        writer.writerow({
            "source_term": data["source_term"],
            "target_term": data["target_term"],
            "type": data["type"],
            "gender": data["gender"] or "",
            "style": data["style"] or "",
            "pronunciation": data["pronunciation"] or "",
            "notes": data["notes"] or "",
            "aliases": "|".join(data["aliases"]),
            "forbidden": "|".join(data["forbidden"]),
            "enabled": "1" if data["enabled"] else "0",
        })
    return buffer.getvalue()


def import_entries(
    raw_entries: list[dict], *, project_id: int = GLOBAL_PROJECT_ID,
) -> tuple[Glossary, list[dict]]:
    """Validate raw dicts into a Glossary.

    Returns (glossary, skipped): conflicting duplicates (same source term,
    different target) and malformed rows are SKIPPED with reasons, never
    merged silently.
    """
    glossary = Glossary()
    skipped: list[dict] = []
    seen: dict[str, str] = {}
    for index, raw in enumerate(raw_entries):
        try:
            data = dict(raw)
            data.setdefault("project_id", project_id)
            entry = GlossaryEntry.from_dict(data)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            skipped.append({"index": index, "term": str(raw.get("source_term")
                            if isinstance(raw, dict) else raw)[:40],
                            "reason": f"malformed: {exc}"})
            continue
        key = entry.source_term.casefold()
        if key in seen and seen[key] != entry.target_term:
            skipped.append({"index": index, "term": entry.source_term,
                            "reason": f"conflict: '{seen[key]}' vs "
                                      f"'{entry.target_term}'"})
            continue
        seen.setdefault(key, entry.target_term)
        glossary.entries.append(entry)
    return glossary, skipped


def import_json(text: str, *,
                project_id: int = GLOBAL_PROJECT_ID) -> tuple[Glossary, list[dict]]:
    """Parse a JSON glossary export (validates format marker)."""
    import json

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"glossary JSON is malformed: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("format") != GLOSSARY_FORMAT:
        raise ValueError("not an almurrib glossary export "
                         "(missing format marker)")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("glossary export has no entries list")
    return import_entries(entries, project_id=project_id)


def import_csv(text: str, *,
               project_id: int = GLOBAL_PROJECT_ID) -> tuple[Glossary, list[dict]]:
    """Parse a CSV glossary export."""
    import csv
    import io

    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except csv.Error as exc:
        raise ValueError(f"glossary CSV is malformed: {exc}") from exc
    raw: list[dict] = []
    for row in rows:
        if not (row.get("source_term") or "").strip():
            continue
        raw.append({
            "source_term": row.get("source_term", "").strip(),
            "target_term": (row.get("target_term") or "").strip(),
            "type": (row.get("type") or "term").strip() or "term",
            "gender": (row.get("gender") or "").strip() or None,
            "style": (row.get("style") or "").strip() or None,
            "pronunciation": (row.get("pronunciation") or "").strip() or None,
            "notes": (row.get("notes") or "").strip() or None,
            "aliases": list(_split_list(row.get("aliases"))),
            "forbidden": list(_split_list(row.get("forbidden"))),
            "enabled": (row.get("enabled") or "1").strip() not in ("0", "false", "no"),
        })
    return import_entries(raw, project_id=project_id)
