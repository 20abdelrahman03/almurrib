"""Ren'Py .rpa archive reader (own implementation, no vendored code).

Format facts verified against the engine's own loader
(``renpy/loader.py`` in Ren'Py 8.5.3 — header layout, XOR deobfuscation,
tuple shapes), never executed, never copied:

* v3 (``RPA-3.0 ``): 40-byte header, hex offset [8:24], hex key [25:33];
  zlib-compressed pickled index at offset; entries are 2-tuples
  ``(offset, dlen)`` or 3-tuples ``(offset, dlen, start)`` with offset/dlen
  XORed by key; ``start`` bytes (when non-empty) are PREPENDED to the chunk.
* v2 (``RPA-2.0 ``): 24-byte header, hex offset [8:]; same index, no XOR.
* v1 (``.rpi``): no magic header, raw zlib + pickle from byte 0.

Security posture (game archives are UNTRUSTED input): the index pickle is
loaded through a restricted unpickler that rejects every global — plain
containers (dict/list/tuple/str/bytes/int) need no globals at all.
Extraction guards path traversal (``..``/absolute names never escape the
destination). unrpa was evaluated and deliberately NOT vendored: GPL-3.0
(combinable, but heavier) and raw ``pickle.loads`` on hostile archives.
"""

from __future__ import annotations

import io
import pickle
import struct
import zlib
from pathlib import Path

from almurrib.core.errors import ExtractionError

_V3_MAGIC = b"RPA-3.0 "
_V2_MAGIC = b"RPA-2.0 "


class _RestrictedUnpickler(pickle.Unpickler):
    """Refuses every global; builtin containers need none."""

    def find_class(self, module: str, name: str):  # noqa: D102
        raise pickle.UnpicklingError(
            f"forbidden global in archive index: {module}.{name}")


def _safe_loads(data: bytes, *, archive: Path):
    try:
        return _RestrictedUnpickler(io.BytesIO(data)).load()
    except Exception as exc:
        raise ExtractionError(
            f"archive index of '{archive}' is not a plain data pickle: {exc}",
            hint="the archive may be corrupt or use an unknown variant.",
        ) from exc


def detect_rpa(path: Path) -> str | None:
    """Return '3.0', '2.0' or None from magic bytes (v1 has no magic)."""
    try:
        with open(path, "rb") as handle:
            magic = handle.read(8)
    except OSError:
        return None
    if magic == _V3_MAGIC:
        return "3.0"
    if magic == _V2_MAGIC:
        return "2.0"
    return None


def read_rpa_index(path: Path) -> tuple[str, dict[str, list[tuple]]]:
    """Read and deobfuscate the file index. Returns (version, index)."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise ExtractionError(f"cannot read archive '{path}': {exc}") from exc
    version = detect_rpa(path)
    try:
        if version == "3.0":
            offset = int(raw[8:24].decode("ascii"), 16)
            key = int(raw[25:33].decode("ascii"), 16)
            payload = zlib.decompress(raw[offset:])
            index = _safe_loads(payload, archive=path)
            out: dict[str, list[tuple]] = {}
            for name, chunks in _as_items(index, path):
                fixed = []
                for chunk in chunks:
                    if len(chunk) == 2:
                        off, length = chunk
                        fixed.append((off ^ key, length ^ key))
                    else:
                        off, length, start = chunk[0], chunk[1], chunk[2]
                        if isinstance(start, str):
                            start = start.encode("latin-1")
                        fixed.append((off ^ key, length ^ key, bytes(start or b"")))
                out[name] = fixed
            return version, out
        if version == "2.0":
            offset = int(raw[8:24].decode("ascii"), 16)
            index = _safe_loads(zlib.decompress(raw[offset:]), archive=path)
            return version, {k: [tuple(c) for c in v]
                             for k, v in _as_items(index, path)}
        # v1 (.rpi): raw zlib + pickle, caught by extension at call sites.
        index = _safe_loads(zlib.decompress(raw), archive=path)
        return "1.0", {k: [tuple(c) for c in v] for k, v in _as_items(index, path)}
    except (ValueError, zlib.error, struct.error) as exc:
        raise ExtractionError(
            f"archive '{path}' is not a readable RPA file: {exc}") from exc


def _as_items(index: object, path: Path) -> list[tuple[str, list]]:
    if not isinstance(index, dict):
        raise ExtractionError(f"archive '{path}' index is not a name map")
    items = []
    for name, chunks in index.items():
        if not isinstance(name, str) or not isinstance(chunks, list):
            raise ExtractionError(f"archive '{path}' has a malformed entry")
        items.append((name, chunks))
    return items


def read_archived_file(archive: Path, name: str) -> bytes:
    """Read one member's bytes (start-prefix + chunk), bounds-checked."""
    version, index = read_rpa_index(archive)
    if name not in index:
        raise ExtractionError(f"'{name}' not found in archive '{archive}'")
    try:
        size = archive.stat().st_size
        data = archive.read_bytes()
    except OSError as exc:
        raise ExtractionError(f"cannot read archive '{archive}': {exc}") from exc
    out = bytearray()
    for chunk in index[name]:
        offset, length = chunk[0], chunk[1]
        prefix = chunk[2] if len(chunk) > 2 else b""
        if not (0 <= offset <= size and 0 <= length
                and offset + length <= size):
            raise ExtractionError(
                f"archive '{archive}' entry '{name}' points outside the file")
        out += bytes(prefix) + data[offset:offset + length]
    _ = version  # v1/v2/v3 converge after index parsing
    return bytes(out)


def extract_all(archive: Path, dest_dir: Path, *,
                suffixes: tuple[str, ...] = (".rpy",)) -> list[Path]:
    """Extract members to ``dest_dir`` (path-traversal guarded).

    Only ``suffixes`` are written (default: scripts); returns written paths
    in sorted order. Names escaping the destination raise ExtractionError.
    """
    _, index = read_rpa_index(archive)
    written: list[Path] = []
    for name in sorted(index):
        if not name.lower().endswith(suffixes):
            continue
        target = (dest_dir / Path(*Path(name).parts)).resolve()
        if target != (dest_dir.resolve() / Path(*Path(name).parts)).resolve() \
                or dest_dir.resolve() not in target.parents:
            raise ExtractionError(
                f"archive '{archive}' entry escapes destination: {name!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(read_archived_file(archive, name))
        written.append(target)
    return written
