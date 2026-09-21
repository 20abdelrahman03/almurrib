"""Misplaced-folder diagnostics (pick a game root, not its data dir)."""

from almurrib.engine_adapters.registry import misplaced_dir_hint


def test_unity_data_dir_suggests_parent(tmp_path):
    data = tmp_path / "Slender_Data"
    data.mkdir()
    hint = misplaced_dir_hint(data)
    assert hint is not None
    assert str(tmp_path) in hint
    assert "game folder instead" in hint


def test_renpy_game_dir_suggests_parent(tmp_path):
    game = tmp_path / "somegame" / "game"
    game.mkdir(parents=True)
    hint = misplaced_dir_hint(game)
    assert hint is not None and str(game.parent) in hint


def test_rpgmaker_data_dir_suggests_parent(tmp_path):
    data = tmp_path / "proj" / "www" / "data"
    data.mkdir(parents=True)
    (tmp_path / "proj" / "Game.rpgproject").write_text("RPGMV 1.0")
    hint = misplaced_dir_hint(data)
    assert hint is not None and str(tmp_path / "proj") in hint


def test_bare_data_dir_no_hint(tmp_path):
    data = tmp_path / "whatever" / "data"
    data.mkdir(parents=True)
    assert misplaced_dir_hint(data) is None


def test_unrelated_dir_no_hint(tmp_path):
    assert misplaced_dir_hint(tmp_path) is None
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert misplaced_dir_hint(nested) is None


def test_cli_detect_surfaces_hint(tmp_path, capsys):
    from almurrib.cli.main import main

    data = tmp_path / "Slender_Data"
    data.mkdir()
    assert main(["detect", str(data)]) == 2
    err = capsys.readouterr().err
    assert "game folder instead" in err
