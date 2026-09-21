"""RPG Maker reinjection: translated data files into a patch directory.

Each entry carries a ``json_path`` (key/index navigation from its file
root, recorded at extraction). Write-back loads the ORIGINAL JSON, sets
translated values at those paths, and mirrors the data layout under
``output_dir`` — the original game is never touched. Untranslated entries
keep their source text (engine falls back naturally); OBSOLETE entries are
excluded by the caller.

Missing files, unreadable JSON, or paths that no longer resolve (game
edited since extraction) raise ExportError listing every failure — never a
partial silent patch.
"""

from __future__ import annotations

import json
from pathlib import Path

from almurrib.core.errors import ExportError
from almurrib.core.model import LocalizationEntry


def _navigate(root: object, path: list) -> tuple[object, object]:
    """Resolve all but the last step; returns (container, last_key)."""
    current = root
    for step in path[:-1]:
        if isinstance(step, int) and isinstance(current, list):
            if 0 <= step < len(current):
                current = current[step]
                continue
        elif isinstance(step, str) and isinstance(current, dict):
            if step in current:
                current = current[step]
                continue
        raise ExportError(
            f"stale json_path (game changed since extraction): {path!r}",
            hint="re-run Extract before exporting.",
        )
    return current, path[-1]


def generate_translated_data(
    entries: list[LocalizationEntry],
    *,
    game_root: Path,
) -> dict[str, str]:
    """Build ``{relative_path: file_content}`` for all translated entries."""
    by_file: dict[str, list[LocalizationEntry]] = {}
    for entry in entries:
        if not entry.translated_text:
            continue
        ref = entry.source_refs[0] if entry.source_refs else None
        if ref is None:
            continue
        by_file.setdefault(ref.file, []).append(entry)

    if not by_file:
        raise ExportError(
            "no translated entries to export",
            hint="run translation first, or check that entries have translated_text.",
        )

    outputs: dict[str, str] = {}
    failures: list[str] = []
    for rel, file_entries in sorted(by_file.items()):
        source = game_root / rel
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            failures.append(f"{rel}: cannot read original ({exc})")
            continue
        for entry in file_entries:
            raw_path = entry.source_refs[0].extra.get("json_path", "")
            try:
                path = json.loads(raw_path)
                container, last = _navigate(document, path)
                if isinstance(last, int) and isinstance(container, list):
                    container[last] = entry.translated_text
                elif isinstance(last, str) and isinstance(container, dict):
                    container[last] = entry.translated_text
                else:
                    raise ExportError(f"stale json_path: {path!r}",
                                      hint="re-run Extract before exporting.")
            except (ValueError, ExportError) as exc:
                failures.append(f"{rel}: {exc}")
        outputs[rel] = json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    if failures:
        raise ExportError(
            "export incomplete:\n" + "\n".join(f"  - {f}" for f in failures),
            hint="re-run Extract, then Export again.",
        )
    return outputs


def write_data_patch(
    entries: list[LocalizationEntry],
    *,
    game_root: Path,
    output_dir: Path,
) -> list[Path]:
    """Write translated data files mirroring the game layout."""
    files = generate_translated_data(entries, game_root=game_root)
    written: list[Path] = []
    for rel, content in files.items():
        target = output_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(target)
    return written
