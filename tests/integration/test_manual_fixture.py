"""Manual-test fixture acceptance (Station 7 browser game).

Validates the fixture as data (graph integrity, glossary format, QA-case
executability) and the test-harness bridges (JSON->rpy->parse roundtrip,
strings.rpy->dialogue_ar mapping). Browser rendering itself is manual.
"""

import json
from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parents[2] / "almurrib_phase2_manual_test"


def _load(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_dialogue_graph_valid():
    data = _load("game_data/dialogue.json")
    nodes = data["nodes"]
    assert 60 <= len(nodes) <= 100
    ids = {n["id"] for n in nodes}
    assert len(ids) == len(nodes)
    assert data["start"] in ids and data["end"] in ids
    texts = [n["text"] for n in nodes]
    texts += [c["text"] for n in nodes for c in n.get("choices", [])]
    assert len(set(texts)) == len(texts)  # bridge maps by exact source
    assert sum(1 for n in nodes if n.get("choices")) >= 10
    seen, stack = set(), [data["start"]]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        node = next(n for n in nodes if n["id"] == cur)
        for choice in node.get("choices", []):
            assert choice["next"] in ids
            stack.append(choice["next"])
        if node.get("next"):
            assert node["next"] in ids
            stack.append(node["next"])
    assert seen == ids  # everything reachable, nothing orphaned


def test_glossary_format_valid_and_rich():
    from almurrib.core.glossary import import_json

    raw = (FIX / "game_data" / "glossary.json").read_text(encoding="utf-8")
    glossary, skipped = import_json(raw)
    assert skipped == []
    assert len(glossary.entries) >= 15
    kinds = {e.type for e in glossary.entries}
    assert {"character", "term"} <= kinds
    assert any(e.gender for e in glossary.entries)
    assert any(e.aliases for e in glossary.entries)
    assert any(e.forbidden for e in glossary.entries)
    assert sum(1 for e in glossary.entries if not e.enabled) >= 1


def test_qa_cases_executable():
    """Every qa_cases.json entry runs through the REAL QA implementation."""
    from almurrib.core.glossary import Glossary, import_json
    from almurrib.arabic.qa import arabic_qa_check
    from almurrib.core.glossary import glossary_qa_check

    cases = _load("game_data/qa_cases.json")["cases"]
    assert len(cases) >= 10
    glossary, _ = import_json(
        (FIX / "game_data" / "glossary.json").read_text(encoding="utf-8"))
    for case in cases:
        result = arabic_qa_check(case["source"], case["translation"],
                                 target_lang=case.get("target_lang", "ar"))
        glossary_flags = glossary_qa_check(
            case["source"], case["translation"],
            glossary.lookup(case["source"]))
        found = {f.rule_id for f in result.flags}
        found |= {f.rule_id for f in glossary_flags}
        expected = case["expected"]
        # Same pass/fail semantics as the translation stage: any error
        # from either engine fails the case.
        passed = result.passed and not any(
            f.severity == "error" for f in glossary_flags)
        assert passed == expected["passed"], case["id"]
        for rule in expected.get("must_flag", []):
            assert rule in found, (case["id"], rule)
        assert case.get("note")


def test_bridge_roundtrip(tmp_path):
    """dialogue.json -> .rpy -> Almurrib parse recovers every string."""
    import subprocess
    import sys

    root = FIX
    rpy_game = root / "rpy"
    assert (rpy_game / "game" / "script.rpy").exists()
    sys.path.insert(0, str(Path("src").resolve()))
    from almurrib.engine_adapters.renpy.parser import parse_rpy

    statements = parse_rpy(rpy_game / "game" / "script.rpy", game_root=rpy_game)
    data = _load("game_data/dialogue.json")
    sources = {n["text"] for n in data["nodes"]}
    sources |= {c["text"] for n in data["nodes"] for c in n.get("choices", [])}
    assert {s.text for s in statements} == sources


def test_typed_player_name_is_display_layer_not_pipeline_bug():
    """Alex-case verdict: EXPECTED behavior, classified.

    The glossary maps "Alex", but pipeline source texts never contain the
    literal "Alex" — only the {player_name} placeholder, which MUST survive
    translation untouched. The Latin name appears when the PLAYER types it
    and the harness substitutes it at display time, after translation.
    Therefore: stored text keeps the placeholder (validation passes), the
    glossary correctly claims no match, and display-time Latin is legitimate.
    """
    from almurrib.core.glossary import import_json
    from almurrib.core.placeholders import validate_translation

    glossary, _ = import_json(
        (FIX / "game_data" / "glossary.json").read_text(encoding="utf-8"))
    source = "Welcome to Station 7, {player_name}!"
    stored = "مرحبا بك في المحطة 7 يا {player_name}!"
    assert glossary.lookup(source) == [] or all(
        m.entry.source_term != "Alex" for m in glossary.lookup(source))
    assert validate_translation(source, stored).ok
    displayed = stored.replace("{player_name}", "Alex")
    assert "Alex" in displayed  # legitimate: typed at display time
    assert "{player_name}" not in displayed


def test_shipped_arabic_output_complete():
    """The committed dialogue_ar.json covers every node (deterministic loop)."""
    data = _load("game_data/dialogue.json")
    ar = _load("output/dialogue_ar.json")["dialogue"]
    assert set(ar) == {n["id"] for n in data["nodes"]}
    for node in data["nodes"]:
        assert "text" in ar[node["id"]]["lines"]
