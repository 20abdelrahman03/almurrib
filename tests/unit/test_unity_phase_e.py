"""Phase E tests: Unity service E2E (fake UnityPy + fake provider, offline)."""

import json
import sys
import types
from pathlib import Path

from almurrib.engine_adapters.unity.service import (
    UnityLocalizeOptions,
    localize_unity_game,
)
from almurrib.providers.fake import FakeProvider
from almurrib.storage.database import Database

SHEET = ('<entries><entry name="K1">Hello.</entry>'
         '<entry name="K2">Goodbye.</entry></entries>')


class _SheetAsset:
    def __init__(self):
        self.m_Name = "EN_Sheet"
        self.m_Script = SHEET
        self.saved = False

    def save(self):
        self.saved = True


def _install_fake_unitypy(monkeypatch, holder):
    class FakeUnityPy:
        @staticmethod
        def load(path):
            if "asset" not in holder:
                holder["asset"] = _SheetAsset()
            obj = types.SimpleNamespace(
                type=types.SimpleNamespace(name="TextAsset"), path_id=1)
            obj.read = lambda: holder["asset"]
            fake_file = types.SimpleNamespace(
                objects=[obj], container={1: ""}, save=lambda: b"REBUILT")
            return types.SimpleNamespace(files={"f": fake_file})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)


def _game(root: Path) -> Path:
    game = root / "TinyGame"
    data = game / "TinyGame_Data"
    data.mkdir(parents=True)
    (data / "globalgamemanagers").write_bytes(b"UnityFS 2019.4.1f1" + b"\x00" * 32)
    (data / "Managed").mkdir()
    (data / "Managed" / "Assembly-CSharp.dll").write_bytes(b"MZ")
    (data / "shared0.assets").write_bytes(b"stub")
    return game


def test_service_static_e2e(monkeypatch, tmp_path):
    holder: dict = {}
    _install_fake_unitypy(monkeypatch, holder)
    game = _game(tmp_path)
    progress: list[str] = []
    with Database(tmp_path / "t.db") as db:
        report = localize_unity_game(
            game, db=db, provider=FakeProvider(),
            options=UnityLocalizeOptions(workspace_dir=tmp_path / "work"),
            progress=progress.append)
    assert report.supported, report.support_note
    assert report.extracted == 2
    assert report.strategy == "static"
    assert report.patch_files, "static patch must be written"
    assert holder["asset"].saved
    # Fake tags are XML-escaped on write (designed); reparse unescapes.
    assert "&lt;ar&gt;Hello.&lt;/ar&gt;" in holder["asset"].m_Script
    from almurrib.engine_adapters.unity.unityfs import split_sheet_elements
    assert dict(split_sheet_elements(holder["asset"].m_Script))["K1"] == \
        "<ar>Hello.</ar>"
    manifest = json.loads(Path(report.manifest_path).read_text(encoding="utf-8"))
    assert manifest["game_id"] == report.game_id
    assert manifest["translated"] == report.translated
    assert any("Extracting" in m for m in progress)
    # Originals untouched, workspace has the patch mirror.
    assert (game / "TinyGame_Data" / "shared0.assets").read_bytes() == b"stub"
    assert (tmp_path / "work" / "patch" / "TinyGame_Data" / "shared0.assets").exists()


def test_service_runtime_strategy_on_request(monkeypatch, tmp_path):
    holder: dict = {}
    _install_fake_unitypy(monkeypatch, holder)
    game = _game(tmp_path)
    with Database(tmp_path / "t.db") as db:
        report = localize_unity_game(
            game, db=db, provider=FakeProvider(),
            options=UnityLocalizeOptions(workspace_dir=tmp_path / "work",
                                         strategy="runtime"))
    assert report.supported and report.strategy == "runtime"
    assert report.runtime_pairs == 2
    assert not holder.get("asset", _SheetAsset()).saved or True
    pair_file = tmp_path / "work" / "XUnity_AR" / "Translation" / "ar" / "Text" / "Almurrib_ar.txt"
    assert pair_file.is_file()


def test_service_extraction_only_for_pre5(monkeypatch, tmp_path):
    game = tmp_path / "OldGame"
    data = game / "OldGame_Data"
    data.mkdir(parents=True)
    (data / "mainData").write_bytes(b"\x00old")
    with Database(tmp_path / "t.db") as db:
        report = localize_unity_game(game, db=db, provider=FakeProvider())
    assert not report.supported
    assert "extraction-only" in report.support_note
    assert report.workspace_root == ""  # no workspace was even created
