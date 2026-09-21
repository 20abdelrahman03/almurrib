"""Phase F tests: §18 Arabic fixture strings + §30 adversarial battery."""

import sys
import types

import pytest

from almurrib.engine_adapters.unity import runtime as R
from almurrib.engine_adapters.unity import workspace as W
from almurrib.engine_adapters.unity.classify import Verdict, classify_candidate
from almurrib.engine_adapters.unity.unityfs import (
    replace_sheet_elements,
    split_sheet_elements,
)

# §18 fixture strings (pipeline handling; true runtime rendering needs the
# Unity editor and is labeled UNVERIFIED in docs).
FIXTURE = [
    "مرحبا بالعالم",
    "مرحبا OpenAI",
    "السعر 123 جنيه",
    "{name} مرحبا",
    "نص عربي طويل " * 40,
    "مرحبا، كيف حالك؟ isn’t it… «نعم»!",
    "Game over: انتهت اللعبة يا Karim!",
    "emoji 🎮🔥 test",
    "https://example.com/لعبة",
]


def test_fixture_classification_sane():
    verdicts = {s: classify_candidate(s).verdict for s in FIXTURE}
    assert verdicts["https://example.com/لعبة"] is Verdict.TECHNICAL
    for s in FIXTURE[:8]:
        assert verdicts[s] is Verdict.LIKELY, s


def test_fixture_sheet_round_trip():
    blob = "<entries>" + "".join(
        f'<entry name="K{i}">{s}</entry>' for i, s in enumerate(FIXTURE[:8])
    ) + "</entries>"
    swaps = {f"K{i}": f"AR-{i}" for i in range(8)}
    new_blob, count = replace_sheet_elements(blob, swaps)
    assert count == 8
    back = dict(split_sheet_elements(new_blob))
    for i in range(8):
        assert back[f"K{i}"] == f"AR-{i}"


def test_fixture_xunity_pairs_parse_back():
    pairs = [(s, f"ترجمة {i}") for i, s in enumerate(FIXTURE[:8])]
    for source, translated in pairs:
        line = f"{R.xunity_encode(source)}={R.xunity_encode(translated)}"
        assert line.count("=") >= 1
        # Encoded newlines/tabs never leak raw control chars into the file.
        assert "\n" not in line and "\r" not in line


def test_arabic_path_workspace(tmp_path):
    game = tmp_path / "لعبة تجريبية"
    data = game / "G_Data"
    data.mkdir(parents=True)
    (data / "globalgamemanagers").write_bytes(b"UnityFS")
    (data / "a.assets").write_bytes(b"bytes")
    ws = W.prepare_workspace(game, tmp_path / "عمل")
    assert W.verify_originals(ws) == []
    W.discard(ws)


def test_repeated_localize_workspace_name_clash(tmp_path):
    game = tmp_path / "G"
    (game / "G_Data").mkdir(parents=True)
    W.prepare_workspace(game, tmp_path / "work")
    with pytest.raises(Exception, match="exists"):
        W.prepare_workspace(game, tmp_path / "work")


def test_corrupted_asset_inspect_reports(monkeypatch, tmp_path):
    bad = tmp_path / "bad.assets"
    bad.write_bytes(b"\x00\x01\x02not a unity file\xff\xfe")

    class FakeUnityPy:
        @staticmethod
        def load(path):
            raise RuntimeError("invalid file header")

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    from almurrib.engine_adapters.unity.unityfs import inspect_asset

    report = inspect_asset(bad)
    assert not report.loadable and "invalid file header" in report.error


def test_malformed_sheet_never_crashes_extract():
    # Entity soup / broken XML must degrade to whole-blob or skip, not crash.
    from almurrib.engine_adapters.unity.unityfs import split_sheet_elements

    assert split_sheet_elements("<entries><entry>no name</entry></entries>") is None
    assert split_sheet_elements("&#38;&#38;") is None
    pairs = split_sheet_elements('<entry name="A">1</entry><entry name="A">2</entry>')
    assert pairs == [("A", "1"), ("A", "2")]
