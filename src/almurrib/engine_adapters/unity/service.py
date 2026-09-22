"""One-click Unity localization service (§22 of the milestone).

``localize_unity_game`` orchestrates the full product flow on SHARED
core services (detect/extract via the pipeline, glossary + TM + QA via
``core.workflow``) plus Unity-only steps (analysis, workspace, strategy,
patch/runtime artifacts, manifest). CLI and GUI both call this — no
workflow logic is duplicated at the edges.

Strategy rule (honest, §29): STATIC patch when parse capabilities are
AUTOMATIC; RUNTIME bundle when they are not (or when static export
fails — the bundle is then still produced as a fallback). A game with
no parse capability at all gets an extraction-only verdict, never a
fake "supported" report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from almurrib import __version__ as _APP_VERSION
from almurrib.core.errors import ExtractionError
from almurrib.core.model import EngineType, EntryStatus
from almurrib.engine_adapters.unity import analysis as _analysis
from almurrib.engine_adapters.unity.analysis import Capability, Level
from almurrib.engine_adapters.unity.workspace import (
    discard,
    prepare_workspace,
    record_modified,
    verify_originals,
)


@dataclass
class UnityLocalizeOptions:
    """Knobs for the service (provider/db travel as arguments)."""

    target_lang: str = "ar"
    source_lang: str = "en"
    project_name: str | None = None
    workspace_dir: Path | None = None  # default: <game>_ar_work
    strategy: str = "auto"  # auto | static | runtime
    force: bool = False
    reuse_machine_tm: bool = False


@dataclass
class UnityLocalizeReport:
    """Everything the GUI/CLI needs to display, no re-computation."""

    game_id: str
    unity_version: str | None
    backend: str
    supported: bool
    support_note: str
    capabilities: list[str] = field(default_factory=list)
    extracted: int = 0
    translated: int = 0
    failed: int = 0
    strategy: str = ""
    patch_files: list[str] = field(default_factory=list)
    runtime_files: list[str] = field(default_factory=list)
    runtime_pairs: int = 0
    manifest_path: str = ""
    workspace_root: str = ""
    warnings: list[str] = field(default_factory=list)


def localize_unity_game(game_dir: Path, *, db, provider,
                        options: UnityLocalizeOptions | None = None,
                        progress=None, log=None) -> UnityLocalizeReport:
    """Run the full Unity flow. See module docstring for the contract."""
    from almurrib.core.pipeline import LocalizationPipeline
    from almurrib.core.workflow import (
        export_translations,
        extract_and_store,
        translate_entries,
    )
    from almurrib.engine_adapters.export import export_for_engine
    from almurrib.engine_adapters.registry import default_adapters
    from almurrib.engine_adapters.unity.runtime import generate_xunity_bundle
    from almurrib.storage.repository import EntryRepository

    options = options or UnityLocalizeOptions()
    game_dir = Path(game_dir)
    emit = progress or (lambda _msg: None)

    emit("Detecting Unity...")
    profile = _analysis.analyze_game(game_dir)
    levels = _analysis.capabilities(profile)
    parse_level = levels[Capability.TEXT_ASSET]
    report = UnityLocalizeReport(
        game_id="", unity_version=profile.unity_version,
        backend=profile.backend.value, supported=False, support_note="",
        capabilities=_analysis.capability_summary(profile))

    if parse_level is Level.UNSUPPORTED:
        report.support_note = (
            "extraction-only verdict: static parsing unsupported for this "
            f"profile ({'; '.join(profile.evidence) or 'no evidence'}). "
            "No patch or runtime bundle was produced.")
        return report

    emit("Preparing safe workspace...")
    workspace_dir = options.workspace_dir or \
        game_dir.parent / f"{game_dir.name}_ar_work"
    workspace = prepare_workspace(game_dir, workspace_dir)
    report.game_id = workspace.game_id
    report.workspace_root = str(workspace.root)

    emit("Extracting...")
    pipeline = LocalizationPipeline(adapters=default_adapters())
    try:
        entries, project_id = extract_and_store(
            pipeline, game_dir, db, target_lang=options.target_lang,
            project_name=options.project_name)
    except ExtractionError as exc:
        # The profile promised nothing: a loud parse failure becomes an
        # honest extraction-only verdict, never a crash.
        discard(workspace)
        report.workspace_root = ""  # discarded; nothing was produced
        report.support_note = (
            f"extraction-only verdict: {exc.message} "
            f"({'; '.join(profile.evidence) or 'no evidence'}).")
        return report
    if not entries:
        discard(workspace)
        report.workspace_root = ""
        report.support_note = (
            "extraction-only verdict: no translatable text found in this "
            f"game ({'; '.join(profile.evidence) or 'no evidence'}).")
        return report
    report.extracted = len(entries)

    emit(f"Translating {len(entries)} entries...")
    stats = translate_entries(
        entries, db, provider, source_lang=options.source_lang,
        target_lang=options.target_lang, project_id=project_id,
        force=options.force, reuse_machine_tm=options.reuse_machine_tm,
        log=log)
    report.translated = (stats.api_translated + stats.memory_hits
                         + stats.cache_hits + stats.already_translated)
    report.failed = stats.failed

    strategy = options.strategy
    if strategy == "auto":
        strategy = "static" if parse_level is Level.AUTOMATIC else "runtime"
    report.strategy = strategy

    repo = EntryRepository(db)
    stored = [e for e in repo.list(project_id=project_id)
              if e.translated_text
              and e.status is not EntryStatus.OBSOLETE]

    if strategy == "static":
        emit("Writing static patch...")
        try:
            written = export_for_engine(
                EngineType.UNITY, game_dir, db,
                output_dir=workspace.root / "patch",
                target_lang=options.target_lang, project_id=project_id)
            report.patch_files = [str(p) for p in written]
            record_modified(
                workspace,
                [str(Path(p).relative_to(workspace.root)) for p in written
                 if _is_relative(p, workspace.root)])
        except Exception as exc:
            report.warnings.append(f"static patch failed ({exc}); "
                                   "runtime bundle produced as fallback.")
            report.strategy = "static+runtime-fallback"
    if report.strategy != "static" or not report.patch_files:
        emit("Generating runtime bundle...")
        bundle = generate_xunity_bundle(
            stored, workspace.root / "XUnity_AR",
            lang=options.target_lang, from_lang=options.source_lang)
        report.runtime_files = bundle.files
        report.runtime_pairs = bundle.pairs
        if bundle.skipped_long:
            report.warnings.append(
                f"{bundle.skipped_long} entries exceed XUnity's 2500-char "
                "limit and were skipped from the runtime bundle.")

    emit("Validating...")
    touched = verify_originals(workspace)
    if touched:
        report.warnings.append(
            "original game files changed during the run: "
            + "; ".join(touched))
    else:
        report.supported = True
        report.support_note = (
            f"{report.strategy} localization ready in the workspace; "
            "original game untouched.")

    manifest_path = workspace.root / "almurrib_patch_manifest.json"
    manifest_path.write_text(json.dumps({
        "almurrib": _APP_VERSION,
        "game_id": workspace.game_id,
        "unity_version": profile.unity_version,
        "backend": profile.backend.value,
        "extracted": report.extracted,
        "translated": report.translated,
        "failed": report.failed,
        "strategy": report.strategy,
        "patch_files": report.patch_files,
        "runtime_files": report.runtime_files,
        "runtime_pairs": report.runtime_pairs,
        "provider": getattr(getattr(provider, "config", None),
                            "identity", "?"),
        "warnings": report.warnings,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    report.manifest_path = str(manifest_path)
    return report


def _is_relative(path, root) -> bool:
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False
