"""RPA reader tests (synthetic archives + hostile inputs).

Test archives are built HERE, byte-by-byte, from the format facts verified
in Ren'Py's own loader source (header layout, XOR, tuple shapes) — no
vendored code, no real .rpa on disk. Real-archive E2E stays UNVERIFIED
until a shipped game archive is available; the format path itself is
engine-source-verified.
"""

import pickle
import struct
import zlib

import pytest

from almurrib.core.errors import ExtractionError
from almurrib.engine_adapters.renpy import rpa


def _build_v3(files: dict[str, bytes], *, key: int = 0x12345678,
              three_tuples: bool = False) -> bytes:
    """Assemble a minimal RPA-3.0 archive (test-only encoder)."""
    from tests.conftest import build_test_rpa_v3

    if not three_tuples:
        return build_test_rpa_v3(files, key=key)
    blob = bytearray(b"RPA-3.0 " + b"0" * 16 + b" " + b"%08x" % key + b"\n")
    index = {}
    for name, content in files.items():
        offset = len(blob)
        blob += content
        index[name] = [(offset ^ key, len(content) ^ key, b"")]
    payload = zlib.compress(pickle.dumps(index))
    offset = len(blob)
    blob += payload
    header = b"RPA-3.0 " + ("%016x" % offset).encode() + b" " + \
        ("%08x" % key).encode() + b"\n"
    return bytes(header) + bytes(blob[len(header):])


def _build_v2(files: dict[str, bytes]) -> bytes:
    blob = bytearray(b"RPA-2.0 " + b"0" * 16 + b"\n")
    index = {}
    for name, content in files.items():
        offset = len(blob)
        blob += content
        index[name] = [(offset, len(content))]
    payload = zlib.compress(pickle.dumps(index))
    offset = len(blob)
    blob += payload
    header = b"RPA-2.0 " + ("%016x" % offset).encode() + b"\n"
    return bytes(header) + bytes(blob[len(header):])


def test_detect_versions(tmp_path):
    v3 = tmp_path / "a.rpa"
    v3.write_bytes(_build_v3({"x.rpy": b"hi"}))
    assert rpa.detect_rpa(v3) == "3.0"
    v2 = tmp_path / "b.rpa"
    v2.write_bytes(_build_v2({"x.rpy": b"hi"}))
    assert rpa.detect_rpa(v2) == "2.0"
    plain = tmp_path / "c.txt"
    plain.write_bytes(b"nope")
    assert rpa.detect_rpa(plain) is None
    assert rpa.detect_rpa(tmp_path / "missing.rpa") is None


def test_v3_index_and_read_two_tuples(tmp_path):
    archive = tmp_path / "a.rpa"
    archive.write_bytes(_build_v3({"s.rpy": b'hi "you"', "o.rpy": b"x" * 5000}))
    version, index = rpa.read_rpa_index(archive)
    assert version == "3.0"
    assert sorted(index) == ["o.rpy", "s.rpy"]
    assert rpa.read_archived_file(archive, "s.rpy") == b'hi "you"'
    assert rpa.read_archived_file(archive, "o.rpy") == b"x" * 5000


def test_v3_three_tuples_with_prefix(tmp_path):
    archive = tmp_path / "a.rpa"
    raw_index = {"s.rpy": [(34, 3, b"PRE")]}
    blob = bytearray(b"RPA-3.0 " + b"0" * 16 + b" " + b"00000000" + b"\n")
    blob += b"abc"
    payload = zlib.compress(pickle.dumps(raw_index))
    offset = len(blob)
    blob += payload
    header = b"RPA-3.0 " + ("%016x" % offset).encode() + b" 00000000\n"
    archive.write_bytes(bytes(header) + bytes(blob[len(header):]))
    assert rpa.read_archived_file(archive, "s.rpy") == b"PREabc"


def test_v2_index_and_read(tmp_path):
    archive = tmp_path / "b.rpa"
    archive.write_bytes(_build_v2({"s.rpy": b"e 'hi'"}))
    version, index = rpa.read_rpa_index(archive)
    assert version == "2.0"
    assert rpa.read_archived_file(archive, "s.rpy") == b"e 'hi'"


def test_extract_all_writes_only_scripts(tmp_path):
    archive = tmp_path / "a.rpa"
    archive.write_bytes(_build_v3({"s.rpy": b"x", "img.png": b"y"}))
    out = tmp_path / "out"
    written = rpa.extract_all(archive, out)
    assert [p.name for p in written] == ["s.rpy"]
    assert (out / "s.rpy").read_bytes() == b"x"


def test_missing_member_raises(tmp_path):
    archive = tmp_path / "a.rpa"
    archive.write_bytes(_build_v3({"s.rpy": b"x"}))
    with pytest.raises(ExtractionError):
        rpa.read_archived_file(archive, "nope.rpy")


def test_malicious_pickle_rejected(tmp_path):
    """A hostile index executing code via pickle globals must fail closed."""

    class Evil:
        def __reduce__(self):
            import os  # noqa: F401 (never executed: must raise first)
            return (eval, ("1+1",))

    archive = tmp_path / "evil.rpa"
    blob = bytearray(b"RPA-3.0 " + b"0" * 16 + b" 00000000\n")
    payload = zlib.compress(pickle.dumps({"s.rpy": [(0, 1), Evil()]}))
    offset = len(blob)
    blob += payload
    header = b"RPA-3.0 " + ("%016x" % offset).encode() + b" 00000000\n"
    archive.write_bytes(bytes(header) + bytes(blob[len(header):]))
    with pytest.raises(ExtractionError):
        rpa.read_rpa_index(archive)


def test_path_traversal_guarded(tmp_path):
    archive = tmp_path / "evil.rpa"
    archive.write_bytes(_build_v3({"../../evil.rpy": b"x"}))
    with pytest.raises(ExtractionError):
        rpa.extract_all(archive, tmp_path / "out")


def test_truncated_archive_raises(tmp_path):
    archive = tmp_path / "bad.rpa"
    archive.write_bytes(b"RPA-3.0 " + b"0" * 40)
    with pytest.raises(ExtractionError):
        rpa.read_rpa_index(archive)
