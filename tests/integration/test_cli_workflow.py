"""CLI workflow tests: translate + export commands (offline)."""

from almurrib.cli.main import main
from almurrib.providers.fake import FakeProvider


def test_translate_command_offline(renpy_fixture_dir, tmp_path, capsys, monkeypatch):
    """`translate` uses the configured provider; we inject the fake one."""
    db_path = tmp_path / "w.db"
    assert main(["extract", str(renpy_fixture_dir), "--db", str(db_path)]) == 0
    capsys.readouterr()

    monkeypatch.setattr("almurrib.cli.main._build_provider", lambda settings: FakeProvider())
    assert main(["translate", "--db", str(db_path)]) == 0
    out = capsys.readouterr().out
    assert "provider      : fake:deterministic-0" in out
    assert "api translations   : 10" in out  # 11 entries, 1 pre-translated
    assert "placeholder issues" not in out

    # second run: everything is already translated â†’ no API calls
    assert main(["translate", "--db", str(db_path)]) == 0
    out = capsys.readouterr().out
    assert "already translated : 11" in out


def test_export_command_produces_renpy_patch(renpy_fixture_dir, tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "w.db"
    out_dir = tmp_path / "patch"
    assert main(["extract", str(renpy_fixture_dir), "--db", str(db_path)]) == 0
    monkeypatch.setattr("almurrib.cli.main._build_provider", lambda settings: FakeProvider())
    assert main(["translate", "--db", str(db_path)]) == 0
    capsys.readouterr()

    assert main(["export", str(renpy_fixture_dir), "--db", str(db_path),
                 "--out", str(out_dir)]) == 0
    out = capsys.readouterr().out
    assert "exported" in out
    assert "NOT modified" in out
    assert (out_dir / "game" / "tl" / "arabic" / "strings.rpy").exists()


def test_localize_command_end_to_end(renpy_fixture_dir, tmp_path, capsys, monkeypatch):
    db_path = tmp_path / "w.db"
    out_dir = tmp_path / "patch"
    monkeypatch.setattr("almurrib.cli.main._build_provider", lambda settings: FakeProvider())

    rc = main(["localize", str(renpy_fixture_dir), "--db", str(db_path),
               "--out", str(out_dir)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "11 extracted" in out
    assert "api translations   : 10" in out
    assert "output        :" in out
    assert (out_dir / "game" / "tl" / "arabic" / "strings.rpy").exists()


def test_translate_without_api_key_fails_clearly(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ALMURRIB_API_KEY", raising=False)
    rc = main(["translate", "--db", str(tmp_path / "x.db")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "auth" in err
    assert "ALMURRIB_API_KEY" in err
