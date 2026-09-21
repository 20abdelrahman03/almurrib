"""Unity engine adapter (UnityPy-backed, optional dependency).

Detection needs no UnityPy (structure + ``UnityFS`` magic sniff). Parsing
and rebuilds need the ``unity`` extra; without it, extraction raises a
clear install error instead of an ImportError traceback.

Scope (honest, documented): TextAsset blobs + MonoBehaviour string fields
up to a bounded size. No IL2CPP/behaviour decompilation, no bundle
rebuilds, no runtime hooks (all Phase 3+ or external-tool territory).
"""

from __future__ import annotations

from pathlib import Path

from almurrib.core.engine import DetectionResult
from almurrib.core.model import (
    EngineType,
    EntryStatus,
    LocalizationEntry,
    SourceRef,
    TranslationSource,
)
from almurrib.engine_adapters.raw import RawStatement
from almurrib.engine_adapters.unity.classify import classify_candidate
from almurrib.engine_adapters.unity.unityfs import (
    UNITYFS_MAGIC,
    UnityDependencyError,
    iter_text_objects,
    sheet_language,
    sniff_version,
    split_sheet_elements,
)


class UnityAdapter:
    """Extraction-first adapter for Unity asset files."""

    @property
    def engine_type(self) -> EngineType:
        return EngineType.UNITY

    # ----- detection ----------------------------------------------------

    def detect(self, game_dir: Path) -> DetectionResult:
        reasons: list[str] = []
        confidence = 0.0
        if not game_dir.is_dir():
            return DetectionResult(self.engine_type, 0.0, ["not a directory"])

        data_dirs = [p for p in game_dir.glob("*_Data") if p.is_dir()]
        manager_files = []
        for data_dir in data_dirs:
            for name in ("globalgamemanagers", "mainData", "data.unity3d"):
                candidate = data_dir / name
                if candidate.is_file():
                    manager_files.append(candidate)
        if manager_files:
            confidence += 0.4
            reasons.append(f"Unity data dir ({manager_files[0].parent.name}/)")
        assets = [p for d in data_dirs for p in d.glob("*.assets")
                  if p.is_file()]
        assets += [p for d in data_dirs for p in d.glob("level*")
                   if p.is_file() and not p.suffix]
        if assets:
            confidence += min(0.4, 0.1 * len(assets))
            reasons.append(f"found {len(assets)} Unity asset file(s)")
            version = sniff_version(manager_files[0]) if manager_files else None
            if version and version != "unknown":
                confidence += 0.05
                reasons.append(f"UnityFS version marker ({version})")
            elif manager_files and self._has_magic(manager_files[0]):
                confidence += 0.05
                reasons.append("UnityFS magic present (version unknown)")
        if list(game_dir.glob("UnityPlayer.dll")):
            confidence += 0.05
            reasons.append("UnityPlayer.dll present")
        return DetectionResult(self.engine_type, min(confidence, 1.0), reasons)

    @staticmethod
    def _has_magic(path: Path) -> bool:
        try:
            return path.read_bytes()[:7] == UNITYFS_MAGIC
        except OSError:
            return False

    # ----- extraction ---------------------------------------------------

    def extract(self, game_dir: Path) -> list[LocalizationEntry]:
        root = game_dir.resolve()
        entries: list[LocalizationEntry] = []
        failures: list[str] = []
        ordinal = 0
        from almurrib.core.errors import ExtractionError

        for asset in self._find_assets(root):
            try:
                objects = iter_text_objects(asset)
            except UnityDependencyError:
                raise
            except ExtractionError as exc:
                # One hostile asset never kills a thousand-file game.
                failures.append(f"{asset.name}: {exc.message}")
                continue
            except Exception as exc:
                failures.append(f"{asset.name}: unexpected ({exc!r})")
                continue
            for found in objects:
                for text, translated, status, provenance, field_path in \
                        self._expand(found):
                    ordinal += 1
                    rel = asset.relative_to(root).as_posix()
                    ref = SourceRef(
                        file=rel, line=ordinal,
                        statement=self._kind(found, field_path),
                        extra={"container": found.container,
                               "class": found.class_name,
                               "field": field_path},
                    )
                    verdict = classify_candidate(
                        text, field_path=field_path,
                        object_name=found.object_name or "",
                        class_name=found.class_name)
                    entries.append(LocalizationEntry(
                        id=LocalizationEntry.make_id(
                            EngineType.UNITY, text, ref),
                        engine=EngineType.UNITY,
                        source_text=text,
                        translated_text=translated,
                        speaker=None,
                        context=f"asset:{rel}; object:{found.object_name or '?'}",
                        status=status,
                        source_refs=[ref],
                        tags=self._tags(found, field_path)
                        + [f"candidate:{verdict.verdict.value}"],
                        metadata={"statement_kind": self._kind(found, field_path),
                                  "class": found.class_name,
                                  "candidate_class": verdict.verdict.value,
                                  "candidate_reason": verdict.reason},
                        translation_source=provenance,
                    ))
        if not entries and failures:
            raise ExtractionError(
                "no Unity text extracted:\n" + "\n".join(f"  - {f}" for f in failures),
                hint="see per-asset causes above; old/compressed variants may apply.",
            )
        return entries

    # Default source sheet language (mirrors the app-wide source_lang default;
    # override per project when adapters accept options in the future).
    SOURCE_SHEET_LANGUAGE = "en"

    @classmethod
    def _expand(cls, found) -> list[tuple]:
        """Split language sheets into keyed entries, or keep whole blobs.

        Returns (text, translated, status, provenance, field_path) tuples:
        * ``EN_*`` sheet elements -> untranslated source entries.
        * other-language sheets -> skipped (not English source).
        * anything else -> the whole blob as one source entry.
        """
        if found.class_name == "TextAsset":
            elements = split_sheet_elements(found.text)
            language = sheet_language(found.object_name)
            if elements and language == cls.SOURCE_SHEET_LANGUAGE:
                return [(value, None, EntryStatus.UNTRANSLATED,
                         TranslationSource.MACHINE.value, f"entry[{key}]")
                        for key, value in elements]
            if elements:
                # Other-language sheets: not English source, not translatable
                # input — skipped (their keys align with EN elements, but
                # without the source language they would mistranslate).
                return []
        return [(found.text, None, EntryStatus.UNTRANSLATED,
                 TranslationSource.MACHINE.value, found.field_path)]

    # ----- helpers ------------------------------------------------------

    @staticmethod
    def _kind(found, field_path: str | None = None) -> str:
        path = field_path if field_path is not None else found.field_path
        if found.class_name == "TextAsset":
            return "sheet_entry" if path.startswith("entry[") else "text_asset"
        return "name" if path.endswith("m_Name") else "field"

    @staticmethod
    def _tags(found, field_path: str | None = None) -> list[str]:
        path = field_path if field_path is not None else found.field_path
        if found.class_name == "TextAsset":
            return ["sheet", "entry"] if path.startswith("entry[") \
                else ["text", "asset"]
        if path.endswith("m_Name"):
            return ["name"]
        return ["field"]

    @staticmethod
    def _find_assets(game_dir: Path) -> list[Path]:
        """All top-level .assets/level files inside *_Data dirs, ordered."""
        found = []
        for data_dir in sorted(p for p in game_dir.glob("*_Data") if p.is_dir()):
            found.extend(sorted(p for p in data_dir.glob("*.assets") if p.is_file()))
            found.extend(sorted(
                p for p in data_dir.glob("level*")
                if p.is_file() and not p.suffix))
        return found
