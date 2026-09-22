"""Shared test fixtures."""

import sys
from pathlib import Path

import pytest

from almurrib.providers.fake import FakeProvider

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


@pytest.fixture(scope="session")
def renpy_fixture_dir() -> Path:
    """Path to the tiny deterministic Ren'Py fixture."""
    return FIXTURES / "renpy_tiny"


class ArabicStubProvider(FakeProvider):
    """FakeProvider whose output passes Arabic QA (TEST ONLY).

    Keeps every placeholder token verbatim and adds real Arabic script,
    so results are ACCEPTED (not FLAGGED) — the honest stand-in for a
    working model in progress/health/persistence tests.
    """

    def _translate_text(self, req) -> str:  # noqa: N802 (matches base name)
        return f"ترجمة عربية: {req.source_text}"


def build_test_rpa_v3(files: dict[str, bytes], *, key: int = 0x12345678) -> bytes:
    """Assemble a minimal RPA-3.0 archive (TEST ONLY).

    Encodes per the format facts verified in Ren'Py's own loader source
    (header layout, XOR deobfuscation, tuple shapes). Used by RPA reader
    tests and packed-game adapter tests alike.
    """
    import pickle
    import zlib

    blob = bytearray(b"RPA-3.0 " + b"0" * 16 + b" " + b"%08x" % key + b"\n")
    assert len(blob) == 34, len(blob)  # 8 magic + 16 offset + 1 + 8 key + \n
    index = {}
    for name, content in files.items():
        offset = len(blob)
        blob += content
        index[name] = [(offset ^ key, len(content) ^ key)]
    payload = zlib.compress(pickle.dumps(index))
    offset = len(blob)
    blob += payload
    header = b"RPA-3.0 " + ("%016x" % offset).encode() + b" " + \
        ("%08x" % key).encode() + b"\n"
    return bytes(header) + bytes(blob[len(header):])
