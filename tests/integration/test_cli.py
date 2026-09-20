"""CLI tests: the observable developer working path."""

from almurrib.cli.main import main


def test_version(capsys):
    assert main(["--version"]) == 0
    assert "almurrib" in capsys.readouterr().out


def test_detect_command(renpy_fixture_dir, capsys):
    assert main(["detect", str(renpy_fixture_dir)]) == 0
    out = capsys.readouterr().out
    assert "renpy" in out
    assert "confidence" in out


def test_extract_then_inspect_and_db(renpy_fixture_dir, tmp_path, capsys):
    db_path = tmp_path / "almurrib.db"
    json_path = tmp_path / "out" / "entries.json"

    assert main(["extract", str(renpy_fixture_dir), "--db", str(db_path),
                 "--json", str(json_path)]) == 0
    out = capsys.readouterr().out
    assert "11 extracted" in out

    assert json_path.exists()
    content = json_path.read_text(encoding="utf-8")
    assert "almurrib-extraction" in content
    assert "Hello! Did you wait long?" in content

    assert main(["inspect", "--db", str(db_path)]) == 0
    out = capsys.readouterr().out
    assert "Hello! Did you wait long?" in out
    assert "اللعبة الصغيرة" in out or "Tiny Fixture" in out

    assert main(["db", "--db", str(db_path)]) == 0
    out = capsys.readouterr().out
    assert "entries        : 11" in out
    assert "translated" in out


def test_extract_rejects_missing_dir(tmp_path, capsys):
    rc = main(["extract", str(tmp_path / "does-not-exist"), "--db", str(tmp_path / "x.db")])
    assert rc == 2
    assert "extract" in capsys.readouterr().err
