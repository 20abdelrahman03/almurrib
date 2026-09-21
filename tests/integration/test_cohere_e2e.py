"""Cohere v2 end-to-end (mocked transport, no key, no network).

Replays the exact user scenario that failed on v1 (75-entry game,
command-a-plus-05-2026): translate the whole fixture through the v2 wire
shape, validate, persist and export — proving the migration works.
"""

import json
import re

from almurrib.core.pipeline import LocalizationPipeline, PipelineContext
from almurrib.core.provider import ProviderConfig
from almurrib.core.translate import RealTranslateStage
from almurrib.core.workflow import extract_and_store, translate_entries
from almurrib.engine_adapters import default_adapters
from almurrib.engine_adapters.renpy.reinject import write_translation_patch
from almurrib.providers.cohere import CohereProvider
from almurrib.storage.database import Database

from pathlib import Path as _Path

GAME = _Path(__file__).resolve().parents[2] / "fixtures" / "the_question"


def _v2_mock(monkeypatch, calls: list):
    import urllib.request

    class _Resp:
        def __init__(self, body: bytes):
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=0):
        calls.append(request.full_url)
        assert request.full_url.endswith("/v2/chat"), request.full_url
        payload = json.loads(request.data.decode())
        user_text = payload["messages"][-1]["content"]
        pairs = re.findall(r"id: ([0-9a-f]{64}) \| text: (.*?)(?: \| |$)",
                           user_text)
        assert pairs, "batch carries no entry ids"
        # Echo the source wrapped (placeholders preserved, like a good model).
        mapping = {i: f"<ar>{t}</ar>" for i, t in pairs}
        body = json.dumps({"message": {"role": "assistant", "content": [
            {"type": "text", "text": json.dumps(mapping, ensure_ascii=False)},
        ]}}).encode()
        return _Resp(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def test_cohere_v2_full_game_e2e(tmp_path, monkeypatch):
    game = GAME
    if not (game / "game" / "script.rpy").exists():
        import pytest

        pytest.skip("the_question fixture not present")
    calls: list = []
    _v2_mock(monkeypatch, calls)

    provider = CohereProvider(ProviderConfig(
        provider="cohere", model="command-a-plus-05-2026",
        base_url="https://api.cohere.com", api_key="test-key",
    ))
    pipeline = LocalizationPipeline(adapters=default_adapters())
    with Database(tmp_path / "e2e.db") as db:
        entries, project_id = extract_and_store(pipeline, game, db)
        assert len(entries) == 75
        stats = translate_entries(entries, db, provider, project_id=project_id)
        assert stats.failed == 0
        assert stats.api_translated == 75
        assert stats.placeholder_failures == 0
        assert provider.last_fallback_calls == 0  # clean v2 batches, no fan-out
        out = tmp_path / "patch"
        written = write_translation_patch(entries, target_lang="ar",
                                          output_dir=out)
    assert written
    content = (out / "game" / "tl" / "ar" / "strings.rpy").read_text(
        encoding="utf-8")
    assert content.count('old "') == 75
    assert calls and all(u.endswith("/v2/chat") for u in calls)
