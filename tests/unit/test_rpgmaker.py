"""RPG Maker adapter tests (MV fixture: detect/extract/write-back)."""

import json

import pytest

from almurrib.core.model import EngineType
from almurrib.engine_adapters.rpgmaker import RPGMakerAdapter
from almurrib.engine_adapters.rpgmaker.parser import find_data_dir
from almurrib.engine_adapters.rpgmaker.reinject import write_data_patch


def test_detect_mv_fixture(tmp_path):
    fixture = tmp_path / "g"
    (fixture / "www" / "data").mkdir(parents=True)
    (fixture / "www" / "data" / "System.json").write_text(
        '{"gameTitle": "X"}', encoding="utf-8")
    result = RPGMakerAdapter().detect(fixture)
    assert result.is_match
    assert result.engine is EngineType.RPGMAKER
    assert "MV" in " ".join(result.reasons)


def test_rpgmaker_detect_rejects_unrelated(tmp_path):
    assert not RPGMakerAdapter().detect(tmp_path).is_match


def test_mz_layout_detected(tmp_path):
    fixture = tmp_path / "g"
    (fixture / "data").mkdir(parents=True)
    (fixture / "data" / "System.json").write_text(
        '{"gameTitle": "X"}', encoding="utf-8")
    (fixture / "data" / "Actors.json").write_text("[null]", encoding="utf-8")
    (fixture / "data" / "Map001.json").write_text("{}", encoding="utf-8")
    result = RPGMakerAdapter().detect(fixture)
    assert result.is_match and "MZ" in " ".join(result.reasons)
    assert find_data_dir(fixture)[1] == "MZ"


def _fixture():
    import pathlib

    fixture = pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "rpgmaker_tiny"
    if not (fixture / "www" / "data" / "System.json").exists():
        import pytest

        pytest.skip("rpgmaker_tiny fixture not present")
    return fixture


def test_extract_fixture():
    fixture = _fixture()
    entries = RPGMakerAdapter().extract(fixture)
    by_text = {e.source_text: e for e in entries}

    assert by_text["Welcome, {player_name}! Our village needs {count} coins."].speaker == "Elder Mira"
    assert by_text["Help the village"].source_refs[0].statement == "menu"
    assert by_text["Tiny Quest"].source_refs[0].statement == "name"
    assert "Potion" in by_text
    # JS plugin line must not leak
    assert not any("$gameVariables" in e.source_text for e in entries)


def test_malformed_json_raises_clearly(tmp_path):
    import pytest

    from almurrib.core.errors import ExtractionError
    from almurrib.engine_adapters.rpgmaker.parser import parse_game

    data = tmp_path / "www" / "data"
    data.mkdir(parents=True)
    (data / "System.json").write_text('{"gameTitle": "X"}', encoding="utf-8")
    (data / "Actors.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ExtractionError):
        parse_game(tmp_path, data)


def test_write_back_round_trip(tmp_path):
    fixture = _fixture()
    entries = RPGMakerAdapter().extract(fixture)
    for entry in entries:
        entry.translated_text = f"<ar>{entry.source_text}</ar>"
    out = tmp_path / "patch"
    written = write_data_patch(entries, game_root=fixture, output_dir=out)
    assert written
    rewritten = json.loads(
        (out / "www" / "data" / "Map001.json").read_text(encoding="utf-8"))
    texts = []

    def collect(node):
        if isinstance(node, dict):
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)
        elif isinstance(node, str) and node.startswith("<ar>"):
            texts.append(node)

    collect(rewritten)
    assert len(texts) == sum(
        1 for e in entries
        if e.source_refs[0].file == "www/data/Map001.json" and e.translated_text)
    # original untouched
    original = json.loads(
        (fixture / "www" / "data" / "Map001.json").read_text(encoding="utf-8"))
    assert not any(isinstance(v, str) and v.startswith("<ar>")
                   for v in str(original))


def test_workflow_end_to_end_dispatch(tmp_path):
    """extract -> translate -> export through shared workflow services."""
    from almurrib.core.pipeline import LocalizationPipeline
    from almurrib.core.workflow import (
        export_translations,
        extract_and_store,
        translate_entries,
    )
    from almurrib.engine_adapters import default_adapters
    from almurrib.providers.fake import FakeProvider
    from almurrib.storage.database import Database

    fixture = _fixture()
    pipeline = LocalizationPipeline(adapters=default_adapters())
    assert pipeline.detect_engine(fixture).engine_type.value == "rpgmaker"
    with Database(tmp_path / "r.db") as db:
        entries, project_id = extract_and_store(pipeline, fixture, db)
        assert len(entries) == 32
        stats = translate_entries(entries, db, FakeProvider(),
                                  project_id=project_id)
        assert stats.failed == 0
        out = tmp_path / "patch"
        written = export_translations(
            pipeline, fixture, db, output_dir=out, target_lang="ar",
            project_id=project_id)
        assert any(p.name == "Map001.json" for p in written)
        rewritten = json.loads(
            (out / "www" / "data" / "Map001.json").read_text(encoding="utf-8"))
        # FakeProvider wraps source text: write-back must carry the
        # provider output verbatim at the recorded json paths.
        assert rewritten["displayName"] == "<ar>Tiny Village</ar>"
        assert rewritten["events"][0]["name"] == "<ar>Elder Mira</ar>"
        assert rewritten["events"][0]["pages"][0]["list"][1][
            "parameters"][0] == "<ar>Welcome, {player_name}! Our village needs {count} coins.</ar>"
        # second run: stable, no API
        again, _ = extract_and_store(pipeline, fixture, db)
        stats2 = translate_entries(again, db, FakeProvider(),
                                   project_id=project_id)
        assert stats2.api_translated == 0


def test_write_back_stale_path_fails(tmp_path):
    from almurrib.core.errors import ExportError
    from almurrib.core.model import LocalizationEntry, SourceRef

    fixture = _fixture()
    ref = SourceRef(file="www/data/Map001.json", line=1, statement="say",
                    extra={"json_path": "[\"nope\", 99]"})
    entry = LocalizationEntry(
        id=LocalizationEntry.make_id(EngineType.RPGMAKER, "x", ref),
        engine=EngineType.RPGMAKER, source_text="x", translated_text="y",
        source_refs=[ref])
    with pytest.raises(ExportError):
        write_data_patch([entry], game_root=fixture, output_dir=tmp_path / "o")
