"""Safe working copies for Unity games (§2, §23 of the milestone).

Originals are NEVER written by default. The flow is::

    original game (read-only analysis)
        -> prepare_workspace()  (copy + sha256 manifest + disk check)
        -> patch / runtime bundle lands in the WORKSPACE or output dir
        -> verify_originals()   (baseline hashes still match)
        -> discard()            (rollback = remove generated artifacts)

Patching the original game folder itself always requires explicit user
confirmation (handled at the CLI/GUI layer, never here).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from almurrib import __version__ as _APP_VERSION
from almurrib.core.errors import ExportError


@dataclass
class Workspace:
    """A prepared working copy plus its manifest."""

    root: Path            # the copied game tree (writable scratch)
    source: Path          # the original game dir (never written)
    game_id: str          # stable identity of the original game
    manifest_path: Path
    files: dict[str, str] = field(default_factory=dict)  # rel -> sha256


def game_identity(game_dir: Path) -> str:
    """Stable game id from layout attributes (not from the path itself).

    Uses data-dir names + manager file sizes + first asset names so the
    id survives moving/renaming the folder but changes when the game
    build actually changes.
    """
    game_dir = game_dir.resolve()
    parts = []
    for data_dir in sorted(p for p in game_dir.glob("*_Data") if p.is_dir()):
        parts.append(data_dir.name)
        for name in ("globalgamemanagers", "mainData", "data.unity3d"):
            candidate = data_dir / name
            if candidate.is_file():
                parts.append(f"{name}:{candidate.stat().st_size}")
        assets = sorted(p.name for p in data_dir.glob("*.assets"))[:5]
        parts.extend(assets)
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:16]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def prepare_workspace(game_dir: Path, dest: Path, *,
                      disk_margin: float = 1.5) -> Workspace:
    """Copy a game into a writable workspace with a hash manifest."""
    source = game_dir.resolve()
    if not source.is_dir():
        raise ExportError(f"game dir not found: '{game_dir}'",
                          hint="point at the folder holding the game exe.")
    dest = dest.resolve()
    if dest.exists():
        raise ExportError(f"workspace destination exists: '{dest}'",
                          hint="remove it or choose another folder.")

    needed = int(_tree_size(source) * disk_margin)
    try:
        free = shutil.disk_usage(dest.parent if dest.parent.exists()
                                 else Path.cwd()).free
    except OSError:
        free = needed  # unmeasurable (odd mounts): proceed, copy will tell
    if free < needed:
        raise ExportError(
            f"not enough disk space (need ~{needed // 1024 // 1024}MB)",
            hint="free space or pick another destination drive.")

    try:
        shutil.copytree(source, dest, copy_function=shutil.copy2)
    except OSError as exc:
        # Disk-full / permission / locked files surface as a clean,
        # actionable error — never a bare traceback (§45).
        raise ExportError(
            f"cannot copy game into workspace: {exc}",
            hint="check disk space, permissions and locked files, "
                 "then retry.",
        ) from exc
    files = {p.relative_to(dest).as_posix(): _hash_file(p)
             for p in sorted(dest.rglob("*")) if p.is_file()}
    manifest = {
        "almurrib": _APP_VERSION,
        "game_id": game_identity(source),
        "source": str(source),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "files": files,
        "modified": [],
    }
    manifest_path = dest / "almurrib_workspace.json"
    manifest_path.write_text(json.dumps(manifest, indent=2),
                             encoding="utf-8")
    return Workspace(root=dest, source=source,
                     game_id=manifest["game_id"],
                     manifest_path=manifest_path, files=files)


def resume_workspace(dest: Path, game_id: str) -> Workspace | None:
    """Reuse a complete workspace from a killed run (§29 resume).

    Returns the Workspace when the destination holds a manifest for the
    SAME game with a complete file set; None otherwise (caller then
    refuses as before). Never trusts a partial copy: the manifest is
    written last, and the file count must match it.
    """
    dest = Path(dest).resolve()
    try:
        workspace = load_workspace(dest)
    except ExportError:
        return None
    if workspace.game_id != game_id:
        return None
    try:
        on_disk = sum(1 for _ in dest.rglob("*") if _.is_file())
    except OSError:
        return None
    # Manifest itself + game files.
    if on_disk < len(workspace.files):
        return None
    return workspace


def load_workspace(root: Path) -> Workspace:
    """Rebuild a Workspace handle from its manifest (§32 rollback).

    Raises ExportError when the directory is not an Almurrib workspace.
    """
    root = Path(root).resolve()
    manifest_path = root / "almurrib_workspace.json"
    if not manifest_path.is_file():
        raise ExportError(f"not an Almurrib workspace: '{root}'",
                          hint="point at a *_ar_work directory.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return Workspace(root=root, source=Path(manifest["source"]),
                     game_id=manifest["game_id"],
                     manifest_path=manifest_path,
                     files=manifest.get("files", {}))


def rollback_workspace(root: Path) -> list[str]:
    """One-action rollback (§32): verify originals, then discard the copy.

    Returns warnings (non-empty means investigate before trusting).
    Originals are verified FIRST so a surprising source change never
    gets silently discarded.
    """
    workspace = load_workspace(root)
    problems = verify_originals(workspace)
    discard(workspace)
    return problems


def verify_originals(workspace: Workspace) -> list[str]:
    """Re-hash the SOURCE tree; return mismatches (empty = untouched)."""
    problems = []
    for rel, expected in workspace.files.items():
        current = workspace.source / rel
        if not current.is_file():
            # Only files that existed in the SOURCE at prepare time are
            # verified; workspace-generated artifacts (manifest, patches)
            # have no source counterpart and are skipped.
            continue
        if _hash_file(current) != expected:
            problems.append(f"{rel}: source hash changed")
    return problems


def record_modified(workspace: Workspace, rel_paths: list[str]) -> None:
    """Append patched outputs to the manifest (audit trail)."""
    manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("modified", []).extend(rel_paths)
    workspace.manifest_path.write_text(json.dumps(manifest, indent=2),
                                       encoding="utf-8")


def discard(workspace: Workspace) -> None:
    """Rollback: remove the whole workspace (originals were never touched)."""
    shutil.rmtree(workspace.root, ignore_errors=True)
