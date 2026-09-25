"""UnityFS access layer (thin UnityPy isolation boundary).

All UnityPy imports live inside functions so the rest of Almurrib imports
cleanly without the optional ``unity`` extra. Callers get
:class:`UnityDependencyError` with install instructions instead of an
ImportError traceback. Detection needs no UnityPy at all (magic sniff).
"""

from __future__ import annotations

import html as _html
import os as _os
import re as _re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from almurrib.core.errors import ExtractionError

UNITYFS_MAGIC = b"UnityFS"
MAX_STRING_LEN = 4096  # longer blobs are data, not dialogue (documented cut)


class UnityDependencyError(ExtractionError):
    """UnityPy (optional ``unity`` extra) is not installed."""

    stage = "extract"


def require_unitypy():
    """Import UnityPy or raise a helpful, stage-tagged error."""
    try:
        import UnityPy  # noqa: F401
    except ImportError as exc:
        import sys as _sys

        if getattr(_sys, "frozen", False):
            hint = ("this app copy was built without Unity support; "
                    "use a current Almurrib.exe (UnityPy ships inside it).")
        else:
            hint = 'install it with: uv pip install "almurrib[unity]"'
        raise UnityDependencyError(
            "Unity support needs the optional UnityPy package",
            hint=hint,
        ) from exc
    import UnityPy

    return UnityPy


@dataclass
class UnityTextObject:
    """One translatable string inside a Unity asset (UnityPy-agnostic shape)."""

    container: str  # asset-internal path (may be "")
    class_name: str  # e.g. "TextAsset", "MonoBehaviour"
    object_name: str
    field_path: str  # dotted typetree path, e.g. "m_Script" or "greeting"
    text: str


def sniff_version(path: Path) -> str | None:
    """Best-effort Unity version probe (magic + header text, stdlib only)."""
    try:
        head = path.read_bytes()[:512]
    except OSError:
        return None
    if not head.startswith(UNITYFS_MAGIC):
        return None
    match = _re.search(rb"20\d\d\.\d+\.[0-9a-z]+", head)
    return match.group(0).decode("ascii", "replace") if match else "unknown"


def iter_text_objects(asset_path: Path) -> list[UnityTextObject]:
    """Enumerate translatable strings (TextAsset + MonoBehaviour strings)."""
    UnityPy = require_unitypy()
    try:
        env = UnityPy.load(str(asset_path))
    except Exception as exc:
        raise ExtractionError(
            f"UnityPy cannot parse '{asset_path}': {exc}",
            hint="the asset may use an unsupported Unity version or compression.",
        ) from exc
    found: list[UnityTextObject] = []
    candidates, failed = 0, 0
    first_error = ""
    for file_path, file in env.files.items():
        objects = file.objects.values() if isinstance(file.objects, dict) \
            else file.objects
        for obj in objects:
            class_name = getattr(obj.type, "name", "?")
            if class_name not in ("TextAsset", "MonoBehaviour"):
                continue
            candidates += 1
            container = ""
            try:
                container = file.container.get(getattr(obj, "path_id", None), "")
            except Exception:
                container = ""
            try:
                if class_name == "TextAsset":
                    asset = obj.read()
                    text = getattr(asset, "m_Script", "")
                    if (isinstance(text, str) and text.strip()
                            and not _is_binary_text(text)):
                        found.append(UnityTextObject(
                            container=str(container),
                            class_name=class_name,
                            object_name=getattr(asset, "m_Name", ""),
                            field_path="m_Script",
                            text=_clean_text(text)))
                    # Empty blobs are legitimate (skipped silently).
                elif class_name == "MonoBehaviour":
                    tree = obj.read_typetree()
                    object_name = tree.get("m_Name", "") if isinstance(tree, dict) else ""
                    for field_path, value in _walk_strings(tree):
                        found.append(UnityTextObject(
                            container=str(container), class_name=class_name,
                            object_name=str(object_name), field_path=field_path,
                            text=value))
            except Exception as exc:
                failed += 1  # one unreadable object never kills the asset
                if not first_error:
                    # No mystery failures: a total blackout always names
                    # its cause (this diagnosed the missing lzma.tpk in
                    # frozen builds — file a bug with this line).
                    first_error = f"{type(exc).__name__}: {exc}"[:300]
    if candidates and not found and failed:
        raise ExtractionError(
            f"Unity asset '{asset_path}' holds {candidates} text object(s) "
            f"but none are readable ({failed} failed)"
            + (f"\nfirst error: {first_error}" if first_error else ""),
            hint="pre-5.x games without embedded typetrees and Mono/.NET "
                 "assembly strings are outside the supported subset — "
                 "unless a first error above names a packaging bug.",
        )
    return found


def _is_binary_text(text: str) -> bool:
    """True for binary blobs masquerading as text (fonts, raw data).

    NUL bytes never occur in real dialogue; a high control-char ratio
    means mis-decoded binary. Such blobs are skipped (documented), never
    sent to translation.
    """
    if "\x00" in text:
        return True
    controls = sum(1 for c in text
                   if unicodedata.category(c) == "Cc" and c not in "\t\n\r")
    return len(text) > 0 and controls / len(text) > 0.3


def _clean_text(text: str) -> str:
    """Replace lone surrogates/unencodables (binary-corrupted asset text).

    Real games ship mis-encoded strings; without this, one bad line crashes
    hashing, SQLite and JSON for the whole run. Replacement is documented
    and visible (U+FFFD), never silent data loss of valid text.
    """
    try:
        text.encode("utf-8")
        return text
    except UnicodeEncodeError:
        return text.encode("utf-8", errors="replace").decode("utf-8")


ENTRY_ELEMENT_RE = _re.compile(r'<entry\s+name="([^"]+)">(.*?)</entry>',
                               _re.DOTALL)
LANG_SHEET_RE = _re.compile(r"^([A-Za-z]{2})_(.*)$")


def split_sheet_elements(text: str) -> list[tuple[str, str]] | None:
    """Split Hollow-Knight-style language sheets into (key, value) pairs.

    Returns None when the text is not sheet-shaped (caller keeps whole-blob
    behavior). Values are XML-entity-unescaped to runtime form (``&lt;page&gt;``
    is the engine's real page-break markup, protected downstream as a tag).
    """
    pairs = [(key, _unescape_entities(value))
             for key, value in ENTRY_ELEMENT_RE.findall(text)]
    return pairs or None


def _unescape_entities(text: str) -> str:
    # Full HTML/XML unescape: game sheets use &lt;/&gt;/&amp; for engine
    # markup AND numeric refs (Hollow Knight: &#39; apostrophes, ~2k uses).
    return _html.unescape(text)


SHEET_FIELD_RE = _re.compile(r"^entry\[(.+)\]$")


def replace_sheet_elements(blob_text: str,
                           swaps: dict[str, str]) -> tuple[str, int]:
    """Swap translated text into sheet ``<entry>`` elements.

    Translations are XML-escaped on write (exact mirror of the unescape
    at extraction: engine markup like ``<page>`` round-trips as
    ``&lt;page&gt;``). Returns     (new_blob, replaced_count); keys absent
    from the blob are left untouched (caller decides staleness policy).
    """
    count = 0

    def _one(match):
        nonlocal count
        key = match.group(1)
        if key in swaps:
            count += 1
            return f'<entry name="{key}">{_xml_escape(swaps[key])}</entry>'
        return match.group(0)

    return ENTRY_ELEMENT_RE.sub(_one, blob_text), count


def _apply_text_asset(asset, container: str,
                      replacements: dict[tuple[str, str, str], str]
                      ) -> list[str]:
    """Apply whole-blob or per-element replacements. Returns problems.

    Stale replacements (key gone / source changed since extraction) are
    reported, never written — a half-patched asset is worse than a loud
    failure.
    """
    blob = getattr(asset, "m_Script", "")
    problems: list[str] = []
    if not isinstance(blob, str) or not blob:
        return problems
    current = dict(split_sheet_elements(blob) or [])
    staged: dict[str, str] = {}
    whole_new: str | None = None
    for (c, f, old), new in replacements.items():
        if c != container:
            continue
        match = SHEET_FIELD_RE.match(f or "")
        if match is None:
            if f == "m_Script" and old == blob:
                whole_new = new
            continue
        key = match.group(1)
        # Object-scoped matching (field-test find on resources.assets):
        # sibling sheets (other languages) share key names but carry
        # different text. A key stages ONLY where key AND old text both
        # match this blob; anything never staged anywhere is reported
        # stale by the caller, not here.
        if key in current and current[key] == old:
            staged[key] = new
    if staged and whole_new is not None:
        problems.append("mixed whole-blob and element replacements")
        whole_new = None
    if staged:
        asset.m_Script, count = replace_sheet_elements(blob, staged)
        if count != len(staged):
            problems.append(f"only {count}/{len(staged)} elements replaced")
        else:
            asset.save()
    elif whole_new is not None:
        asset.m_Script = whole_new
        asset.save()
    return problems


def unapplied_element_keys(asset_blobs: list[tuple[str, str]],
                           replacements: dict[tuple[str, str, str], str]
                           ) -> list[str]:
    """Element keys no blob accepted (genuinely stale translations).

    ``asset_blobs`` is (container, m_Script) per TextAsset object.
    Called after all objects so sibling-language sheets had their chance.
    """
    wanted: dict[tuple[str, str, str], str] = {}
    for (c, f, old), new in replacements.items():
        match = SHEET_FIELD_RE.match(f or "")
        if match is not None:
            wanted[(c, match.group(1), old)] = new
    for container, blob in asset_blobs:
        if not isinstance(blob, str) or not blob:
            continue
        current = dict(split_sheet_elements(blob) or [])
        for key in list(wanted):
            c, k, old = key
            if c == container and current.get(k) == old:
                del wanted[key]
    return [f"entry[{k}]: no sheet holds this source text (stale?)"
            for (_, k, _) in wanted]


def sheet_language(object_name: str) -> str | None:
    """Two-letter sheet prefix (``EN_Banker`` -> ``en``), else None."""
    match = LANG_SHEET_RE.match(object_name or "")
    return match.group(1).lower() if match else None


def _walk_strings(node: object, prefix: str = "") -> list[tuple[str, str]]:
    """Collect (dotted path, text) for bounded string leaves."""
    out: list[tuple[str, str]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.extend(_walk_strings(value, path))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            out.extend(_walk_strings(value, f"{prefix}[{index}]"))
    elif isinstance(node, str) and node.strip() and len(node) <= MAX_STRING_LEN:
        if not _is_binary_text(node):
            out.append((prefix, _clean_text(node)))
    return out


def apply_translations(asset_path: Path, replacements: dict[tuple[str, str, str], str],
                       *, dest_path: Path) -> Path:
    """Write a translated COPY of an asset (originals never touched).

    ``replacements`` maps (container, field_path, old_text) -> new_text,
    where field_path is ``m_Script`` (whole blob), ``entry[KEY]`` (sheet
    element) or a MonoBehaviour typetree path. Anything unmapped keeps
    source text. Stale element replacements refuse the whole file loudly.
    Returns the written path.
    """
    UnityPy = require_unitypy()
    try:
        env = UnityPy.load(str(asset_path))
    except Exception as exc:
        raise ExtractionError(
            f"UnityPy cannot parse '{asset_path}': {exc}") from exc
    def _objects(file):
        # UnityPy hands dicts (path_id -> reader) or plain lists depending
        # on file kind — iterating a dict yields int keys (field-test find
        # on resources.assets: "'int' object has no attribute 'type'").
        objs = file.objects
        return objs.values() if isinstance(objs, dict) else objs

    problems: list[str] = []
    blobs: list[tuple[str, str]] = []
    for _, file in env.files.items():
        for obj in _objects(file):
            class_name = getattr(obj.type, "name", "?")
            try:
                container = str(file.container.get(getattr(obj, "path_id", None), ""))
            except Exception:
                container = ""
            try:
                if class_name == "TextAsset":
                    asset = obj.read()
                    # Snapshot BEFORE applying: staleness is judged against
                    # original sources, never our own translations.
                    blobs.append((container,
                                  getattr(asset, "m_Script", "")))
                    asset_problems = _apply_text_asset(
                        asset, container, replacements)
                    problems.extend(
                        f"{container or '?'}:{p}" for p in asset_problems)
                elif class_name == "MonoBehaviour":
                    tree = obj.read_typetree()
                    if _apply_tree(tree, container, replacements):
                        obj.save_typetree(tree)
            except Exception:
                continue
    problems.extend(unapplied_element_keys(blobs, replacements))
    if problems:
        raise ExtractionError(
            f"Unity asset '{asset_path}' write-back refused:\n" +
            "\n".join(f"  - {p}" for p in problems),
            hint="re-extract, re-translate, then retry export.",
        )
    # Capability-based (no fragile type imports): any loaded file object
    # whose save() returns bytes is rebuildable. Bundle inputs need
    # bundle-aware rebuilds (documented limitation) and are skipped.
    # Atomic output (§13): stage to a temp sibling, validate by reparse
    # (§31), then replace — a failed validation never leaves a
    # half-patched file behind.
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    for _, file in env.files.items():
        save = getattr(file, "save", None)
        if not callable(save):
            continue
        try:
            payload = save()
        except TypeError:
            continue  # e.g. bundle save() needing a packer argument
        except Exception as exc:
            raise ExtractionError(
                f"UnityPy cannot rebuild '{asset_path}': {exc}") from exc
        if not isinstance(payload, (bytes, bytearray)):
            continue
        staging = dest_path.with_name(dest_path.name + ".tmp")
        staging.write_bytes(bytes(payload))
        try:
            validate_patch(staging)
        except ExtractionError:
            try:
                staging.unlink()
            except OSError:
                pass
            raise
        _os.replace(staging, dest_path)
        return dest_path
    raise ExtractionError(
        f"no rebuildable Unity asset file inside '{asset_path}'",
        hint="asset bundles (.ab) need bundle-aware rebuilds (unsupported).")


def validate_patch(staged: Path) -> int:
    """Re-parse a rebuilt asset; return its object count (§31).

    Raises ExtractionError when the output does not load — the caller
    must then refuse to place it (atomicity).
    """
    UnityPy = require_unitypy()
    try:
        # From memory, not from the path: UnityPy keeps source files
        # open, and Windows refuses to move/rename an open file
        # (field-test find: WinError 32 on os.replace after reparse).
        env = UnityPy.load(staged.read_bytes())
    except Exception as exc:
        raise ExtractionError(
            f"rebuilt asset '{staged.name}' does not re-parse: {exc}",
            hint="the patch was discarded; originals untouched.",
        ) from exc
    total = 0
    try:
        for _, file in env.files.items():
            objects = file.objects.values() \
                if isinstance(file.objects, dict) else file.objects
            total += sum(1 for _ in objects)
    except Exception as exc:
        raise ExtractionError(
            f"rebuilt asset '{staged.name}' census failed: {exc}") from exc
    return total


@dataclass
class AssetReport:
    """What UnityPy can say about one asset file (read-only probe)."""

    path: str
    loadable: bool
    object_count: int = 0
    classes: dict[str, int] | None = None
    error: str = ""


def inspect_asset(asset_path: Path) -> AssetReport:
    """Census one asset/bundle file without translating anything.

    Never raises for a merely-unreadable file: ``loadable=False`` plus
    the error carries the precise diagnostic (used by CLI inspect and
    failure reports).
    """
    UnityPy = require_unitypy()
    report = AssetReport(path=str(asset_path), loadable=False)
    try:
        env = UnityPy.load(str(asset_path))
    except Exception as exc:
        report.error = f"UnityPy cannot parse: {exc}"
        return report
    census: Counter[str] = Counter()
    total = 0
    try:
        for _, file in env.files.items():
            objects = file.objects.values() \
                if isinstance(file.objects, dict) else file.objects
            for obj in objects:
                census[getattr(obj.type, "name", "?")] += 1
                total += 1
    except Exception as exc:
        report.error = f"object census failed: {exc}"
        return report
    report.loadable = True
    report.object_count = total
    report.classes = dict(census)
    return report


def _apply_tree(node: object, container: str,
                replacements: dict[tuple[str, str, str], str],
                prefix: str = "") -> bool:
    """Set translated strings inside a typetree dict. Returns changed flag."""
    changed = False
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, str):
                lookup = (container, path, value)
                if lookup in replacements:
                    node[key] = replacements[lookup]
                    changed = True
            else:
                changed |= _apply_tree(value, container, replacements, path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            path = f"{prefix}[{index}]"
            if isinstance(value, str):
                lookup = (container, path, value)
                if lookup in replacements:
                    node[index] = replacements[lookup]
                    changed = True
            else:
                changed |= _apply_tree(value, container, replacements, path)
    return changed
