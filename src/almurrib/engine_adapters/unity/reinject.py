"""Unity reinjection: translated asset copies into a patch directory.

Each entry's ``SourceRef.extra`` carries (container, class, field), recorded
at extraction. Write-back loads the ORIGINAL asset, applies translations by
that triple plus the source text, and saves a rebuilt COPY mirroring the
game layout — originals are never touched (delete the patch to roll back).
Entries UnityPy cannot round-trip raise ExportError instead of writing a
half-patched asset.
"""

from __future__ import annotations

from pathlib import Path

from almurrib.core.errors import ExportError, ExtractionError
from almurrib.core.model import LocalizationEntry
from almurrib.engine_adapters.unity.unityfs import apply_translations


def write_asset_patch(
    entries: list[LocalizationEntry],
    *,
    game_root: Path,
    output_dir: Path,
) -> list[Path]:
    """Rebuild translated asset files mirroring the game layout."""
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

    written: list[Path] = []
    failures: list[str] = []
    for rel, file_entries in sorted(by_file.items()):
        source = game_root / rel
        if not source.is_file():
            failures.append(f"{rel}: original asset missing")
            continue
        replacements = {}
        for entry in file_entries:
            extra = entry.source_refs[0].extra
            replacements[(extra.get("container", ""),
                          extra.get("field", ""),
                          entry.source_text)] = entry.translated_text or ""
        try:
            written.append(apply_translations(
                source, replacements, dest_path=output_dir / rel))
        except (ExportError, ExtractionError) as exc:
            failures.append(f"{rel}: {exc}")
        except Exception as exc:
            # UnityPy internals on hostile assets: collected into the
            # report (which fails the export loudly), never a bare crash.
            failures.append(f"{rel}: unexpected rebuild failure ({exc!r})")
    if failures:
        raise ExportError(
            "export incomplete:\n" + "\n".join(f"  - {f}" for f in failures),
            hint="translate/extract again, then retry export.",
        )
    return written
