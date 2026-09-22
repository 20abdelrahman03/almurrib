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


def test_translate_force_retranslates_everything(renpy_fixture_dir, tmp_path,
                                                 capsys, monkeypatch):
    """--force must actually reach the stage (regression: flag was dropped)."""
    db_path = tmp_path / "w.db"
    assert main(["extract", str(renpy_fixture_dir), "--db", str(db_path)]) == 0
    monkeypatch.setattr("almurrib.cli.main._build_provider", lambda settings: FakeProvider())
    assert main(["translate", "--db", str(db_path)]) == 0
    capsys.readouterr()
    assert main(["translate", "--db", str(db_path), "--force"]) == 0
    out = capsys.readouterr().out
    assert "force" in out
    assert "api translations   : 11" in out  # all, incl. pre-translated


def test_translate_scoped_to_game_dir(renpy_fixture_dir, tmp_path, capsys, monkeypatch):
    import shutil

    other = tmp_path / "othergame"
    shutil.copytree(renpy_fixture_dir, other)
    db_path = tmp_path / "w.db"
    assert main(["extract", str(renpy_fixture_dir), "--db", str(db_path)]) == 0
    assert main(["extract", str(other), "--db", str(db_path)]) == 0
    monkeypatch.setattr("almurrib.cli.main._build_provider", lambda settings: FakeProvider())
    capsys.readouterr()
    assert main(["translate", "--db", str(db_path),
                 "--game-dir", str(renpy_fixture_dir)]) == 0
    out = capsys.readouterr().out
    assert "entries       : 11" in out  # only this project's entries


def test_clear_then_retranslate_cycle(renpy_fixture_dir, tmp_path, capsys,
                                      monkeypatch):
    """Clean slate for model comparison: clear -> fresh API run -> export."""
    from almurrib.core.workflow import translate_entries
    from almurrib.storage.database import Database
    from almurrib.storage.repository import EntryRepository

    db_path = tmp_path / "w.db"
    assert main(["extract", str(renpy_fixture_dir), "--db", str(db_path)]) == 0
    monkeypatch.setattr("almurrib.cli.main._build_provider", lambda settings: FakeProvider())
    assert main(["translate", "--db", str(db_path)]) == 0
    capsys.readouterr()

    assert main(["clear", "--db", str(db_path),
                 "--game-dir", str(renpy_fixture_dir)]) == 0
    out = capsys.readouterr().out
    assert "cleared 11 translation(s)" in out  # 10 fresh + 1 imported pair

    with Database(db_path) as db:
        repo = EntryRepository(db)
        assert all(e.translated_text is None for e in repo.list())
        # the pre-existing imported pair is current (not obsolete) -> cleared too
        stats = translate_entries(repo.list(), db, FakeProvider())
        assert stats.api_translated == 11  # everything goes to the provider


def test_clear_refuses_unguarded_scope(tmp_path, capsys):
    rc = main(["clear", "--db", str(tmp_path / "x.db")])
    assert rc == 2
    assert "specify --game-dir or --all" in capsys.readouterr().err


def test_glossary_cli_crud_and_import(tmp_path, capsys):
    db_path = tmp_path / "g.db"
    assert main(["glossary", "add", "--db", str(db_path),
                 "--source", "Sylvie", "--target", "سيلفي",
                 "--type", "character", "--gender", "female"]) == 0
    assert main(["glossary", "list", "--db", str(db_path)]) == 0
    out = capsys.readouterr().out
    assert "Sylvie -> سيلفي" in out and "character" in out

    # conflict refused
    rc = main(["glossary", "add", "--db", str(db_path),
               "--source", "sylvie", "--target", "غير"])
    assert rc == 2

    # JSON round trip through files
    export = tmp_path / "gloss.json"
    assert main(["glossary", "export", "--db", str(db_path),
                 "--file", str(export)]) == 0
    assert main(["glossary", "clear", "--db", str(db_path)]) == 0
    assert main(["glossary", "import", "--db", str(db_path),
                 "--file", str(export)]) == 0
    capsys.readouterr()
    assert main(["glossary", "list", "--db", str(db_path)]) == 0
    assert "Sylvie -> سيلفي" in capsys.readouterr().out

    # missing file / bad scope guarded
    assert main(["glossary", "import", "--db", str(db_path)]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text('{"nope": true}', encoding="utf-8")
    assert main(["glossary", "import", "--db", str(db_path),
                 "--file", str(bad)]) == 2


def test_translate_total_failure_exit_code(tmp_path, capsys, monkeypatch):
    from almurrib.core.errors import RateLimitError
    from almurrib.providers.fake import FakeProvider as _Fake

    class _Down(_Fake):
        def translate_batch(self, requests):
            raise RateLimitError("rate limit exceeded (HTTP 429)",
                                 http_status=429,
                                 provider_message="slow down")

    db_path = tmp_path / "w.db"
    from almurrib.cli.main import main as _main

    # extract via a tiny inline game
    game = tmp_path / "g"
    (game / "game").mkdir(parents=True)
    (game / "game" / "script.rpy").write_text(
        'label start:\n    "Hello."\n', encoding="utf-8")
    assert _main(["extract", str(game), "--db", str(db_path)]) == 0
    monkeypatch.setattr("almurrib.cli.main._build_provider", lambda settings: _Down())
    capsys.readouterr()
    rc = _main(["translate", "--db", str(db_path)])
    assert rc == 2  # nothing translated at all
    err = capsys.readouterr().err
    assert "HTTP Status: 429" in err
    assert "Suggestion:" in err
