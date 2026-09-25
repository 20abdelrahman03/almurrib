"""Unity CLI acceptance tests (§43, scripted — no manual helper scripts)."""

import sys
import types

from almurrib.cli.main import main
from tests.conftest import ArabicStubProvider

SHEET = ('<entries><entry name="K1">Hello.</entry>'
         '<entry name="K2">Goodbye.</entry></entries>')


class _SheetAsset:
    def __init__(self, script=SHEET):
        self.m_Name = "EN_Sheet"
        self.m_Script = script
        self.saved = False

    def save(self):
        self.saved = True


def _install_fake_unitypy(monkeypatch, blob=SHEET):
    holder = {}

    class FakeUnityPy:
        @staticmethod
        def load(path):
            if "asset" not in holder:
                holder["asset"] = _SheetAsset(blob)
            obj = types.SimpleNamespace(
                type=types.SimpleNamespace(name="TextAsset"), path_id=1)
            obj.read = lambda: holder["asset"]
            fake_file = types.SimpleNamespace(
                objects=[obj], container={1: ""}, save=lambda: b"REBUILT")
            return types.SimpleNamespace(files={"f": fake_file})

    monkeypatch.setitem(sys.modules, "UnityPy", FakeUnityPy)
    return holder


def _game(root):
    game = root / "TinyGame"
    data = game / "TinyGame_Data"
    data.mkdir(parents=True)
    (data / "globalgamemanagers").write_bytes(b"UnityFS 2019.4.1f1" + b"\x00" * 32)
    (data / "Managed").mkdir()
    (data / "Managed" / "Assembly-CSharp.dll").write_bytes(b"MZ")
    (data / "shared0.assets").write_bytes(b"stub")
    return game


def test_unity_scan_counts_without_provider(tmp_path, capsys, monkeypatch):
    _install_fake_unitypy(monkeypatch)
    game = _game(tmp_path)
    db = tmp_path / "u.db"
    assert main(["unity", "scan", str(game), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "extracted       : 2" in out
    assert "unique strings  : 2" in out
    assert "duplicate occurrences: 0" in out


def test_unity_preflight_gates_and_reports(tmp_path, capsys, monkeypatch):
    _install_fake_unitypy(monkeypatch)
    monkeypatch.setattr("almurrib.cli.main._build_provider",
                        lambda settings: ArabicStubProvider())
    game = _game(tmp_path)
    db = tmp_path / "u.db"
    assert main(["unity", "scan", str(game), "--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["unity", "preflight", str(game), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "canary          : PASS" in out


def test_unity_explain_finds_entry(tmp_path, capsys, monkeypatch):
    _install_fake_unitypy(monkeypatch)
    game = _game(tmp_path)
    db = tmp_path / "u.db"
    assert main(["unity", "scan", str(game), "--db", str(db)]) == 0
    capsys.readouterr()
    assert main(["unity", "explain", "--db", str(db),
                 "--game-dir", str(game), "--contains", "Hello"]) == 0
    out = capsys.readouterr().out
    assert "Hello." in out and "PENDING" in out


def test_unity_rollback_removes_workspace(tmp_path, capsys):
    from almurrib.engine_adapters.unity.workspace import prepare_workspace

    game = _game(tmp_path)
    ws = prepare_workspace(game, tmp_path / "work")
    assert ws.root.is_dir()
    capsys.readouterr()
    assert main(["unity", "rollback", str(ws.root)]) == 0
    out = capsys.readouterr().out
    assert "verified untouched" in out
    assert not ws.root.exists()


def test_unity_verify_reports_patch(tmp_path, capsys, monkeypatch):
    _install_fake_unitypy(monkeypatch)
    from almurrib.engine_adapters.unity.workspace import prepare_workspace

    game = _game(tmp_path)
    ws = prepare_workspace(game, tmp_path / "work")
    patch = ws.root / "patch" / "TinyGame_Data"
    patch.mkdir(parents=True)
    (patch / "shared0.assets").write_bytes(b"stub")
    assert main(["unity", "verify", str(ws.root)]) == 0
    out = capsys.readouterr().out
    assert "verified        : 1/1" in out
