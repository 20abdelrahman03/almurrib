"""Pipeline tests."""

import pytest

from almurrib.core.errors import DetectionError
from almurrib.core.model import EngineType
from almurrib.core.pipeline import LocalizationPipeline, PipelineContext
from almurrib.engine_adapters import default_adapters


def test_detect_engine(renpy_fixture_dir):
    pipeline = LocalizationPipeline(adapters=default_adapters())
    adapter = pipeline.detect_engine(renpy_fixture_dir)
    assert adapter.engine_type is EngineType.RENPY


def test_detect_fails_clearly_for_unknown_dir(tmp_path):
    pipeline = LocalizationPipeline(adapters=default_adapters())
    with pytest.raises(DetectionError):
        pipeline.detect_engine(tmp_path)


def test_extract_flow_produces_normalized_entries(renpy_fixture_dir):
    pipeline = LocalizationPipeline(adapters=default_adapters())
    context = PipelineContext(game_dir=renpy_fixture_dir)
    result = pipeline.extract(renpy_fixture_dir, context)

    assert result.files_scanned >= 2
    assert len(result.entries) == 11
    # normalize stage guarantees deterministic ordering
    refs = [(e.source_refs[0].file, e.source_refs[0].line) for e in result.entries]
    assert refs == sorted(refs)


def test_pipeline_accepts_custom_translate_stage(renpy_fixture_dir):
    """The Translate interface is pluggable *now* — proven with a stub."""

    class StubTranslator:
        name = "translate"

        def translate(self, result, context):
            for entry in result.entries:
                if entry.translated_text is None:
                    entry.translated_text = f"<{context.target_lang}:{entry.source_text}>"
            return result

    pipeline = LocalizationPipeline(adapters=default_adapters(), translate=StubTranslator())
    context = PipelineContext(game_dir=renpy_fixture_dir, target_lang="ar")
    result = pipeline.extract(renpy_fixture_dir, context)
    assert all(e.translated_text for e in result.entries)
