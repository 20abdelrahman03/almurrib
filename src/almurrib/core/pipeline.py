"""Pipeline abstraction.

Represents the flow:

    Detect -> Extract -> Normalize -> Translate -> Validate -> Export/Rebuild

Only the first half (Detect, Extract, Normalize, Export) has real
implementations in this task. ``Translate`` and ``Validate`` exist as
interfaces plus no-op defaults so later phases plug in without reshaping
the architecture (future-proof the contract, not the whole system).

The pipeline core is engine-agnostic: engine behavior arrives through
:class:`~almurrib.core.engine.EngineAdapter` implementations, so nothing
Ren'Py-specific leaks into the general flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from almurrib.core.engine import EngineAdapter
from almurrib.core.errors import DetectionError, ExtractionError, PipelineError
from almurrib.core.model import LocalizationEntry


@dataclass
class PipelineContext:
    """Shared, explicit state carried between stages.

    No hidden globals: anything a stage needs is passed through here.
    """

    game_dir: Path
    target_lang: str = "ar"
    source_lang: str = "en"
    project_name: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Output of the Extract+Normalize stages."""

    entries: list[LocalizationEntry]
    files_scanned: int = 0


@runtime_checkable
class PipelineStage(Protocol):
    """Smallest composable unit of the pipeline."""

    @property
    def name(self) -> str: ...

    def run(self, context: PipelineContext) -> PipelineContext: ...


class DetectStage:
    """Stage 1: choose the right engine adapter for a game directory."""

    name = "detect"

    def __init__(self, adapters: list[EngineAdapter]) -> None:
        self._adapters = adapters

    def detect(self, game_dir: Path) -> EngineAdapter:
        results = []
        for adapter in self._adapters:
            result = adapter.detect(game_dir)
            if result.is_match:
                results.append(result)
        if not results:
            raise DetectionError(
                f"no engine adapter recognized '{game_dir}'",
                hint="supported engines right now: "
                + ", ".join(a.engine_type.value for a in self._adapters),
            )
        best = max(results, key=lambda r: r.confidence)
        for adapter in self._adapters:
            if adapter.engine_type is best.engine:
                return adapter
        raise PipelineError(f"adapter for detected engine '{best.engine.value}' not registered")

class TranslateStage(Protocol):
    """Stage 4 (interface only): translate entries.

    Implemented in the second half of Phase 1 (llama.cpp + Qwen 2.5,
    optional BYO-key cloud providers). The cache hooks in here.
    """

    name = "translate"

    def translate(self, result: ExtractionResult, context: PipelineContext) -> ExtractionResult: ...


class NoOpTranslateStage:
    """Placeholder translator: passes entries through untouched.

    Keeps the pipeline shape honest without pretending to translate.
    """

    name = "translate"

    def translate(self, result: ExtractionResult, context: PipelineContext) -> ExtractionResult:
        return result


class ValidateStage(Protocol):
    """Stage 5 (interface only): QA over translated entries (Phase 2)."""

    name = "validate"

    def validate(self, result: ExtractionResult, context: PipelineContext) -> ExtractionResult: ...


class NoOpValidateStage:
    name = "validate"

    def validate(self, result: ExtractionResult, context: PipelineContext) -> ExtractionResult:
        return result


class LocalizationPipeline:
    """Composes the stages into the working first-half flow."""

    def __init__(
        self,
        adapters: list[EngineAdapter],
        translate: TranslateStage | None = None,
        validate: ValidateStage | None = None,
    ) -> None:
        self._detect = DetectStage(adapters)
        self._translate = translate or NoOpTranslateStage()
        self._validate = validate or NoOpValidateStage()

    def detect_engine(self, game_dir: Path) -> EngineAdapter:
        return self._detect.detect(game_dir)

    def extract(self, game_dir: Path, context: PipelineContext | None = None) -> ExtractionResult:
        """Run Detect -> Extract -> Normalize (the implemented half)."""
        if not game_dir.exists():
            raise ExtractionError(
                f"game directory does not exist: '{game_dir}'",
                hint="pass the root of the game/project, e.g. the folder containing 'game/'.",
            )
        context = context or PipelineContext(game_dir=game_dir)
        adapter = self._detect.detect(game_dir)
        result = ExtractStage(adapter).extract(game_dir)
        result = NormalizeStage().normalize(result)
        # No-op today, real in Phase 1b / Phase 2 — kept in the flow so the
        # shape of the full pipeline is already visible and testable.
        result = self._translate.translate(result, context)
        result = self._validate.validate(result, context)
        return result



class ExtractStage:
    """Stage 2: run the adapter's extraction."""

    name = "extract"

    def __init__(self, adapter: EngineAdapter) -> None:
        self._adapter = adapter

    def extract(self, game_dir: Path) -> ExtractionResult:
        entries = self._adapter.extract(game_dir)
        files = {ref.file for entry in entries for ref in entry.source_refs}
        return ExtractionResult(entries=entries, files_scanned=len(files))


class NormalizeStage:
    """Stage 3: deterministic post-processing of extracted entries.

    Engine adapters already emit the normalized model; this stage only
    applies cross-engine deterministic rules (deduplication bookkeeping,
    ordering) so extraction results are reproducible byte-for-byte.
    """

    name = "normalize"

    def normalize(self, result: ExtractionResult) -> ExtractionResult:
        # Stable ordering: by source file, then line, then text.
        def sort_key(entry: LocalizationEntry) -> tuple[str, int, str]:
            ref = entry.source_refs[0] if entry.source_refs else None
            return (ref.file if ref else "", ref.line if ref else 0, entry.source_text)

        result.entries.sort(key=sort_key)
        return result
