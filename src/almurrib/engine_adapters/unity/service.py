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
    game_identity,
    prepare_workspace,
    record_modified,
    resume_workspace,
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
    # Legacy Unity renderers need pre-shaped visual order (see visual.py).
    # Default ON for Unity; the DB always keeps logical text.
    visual_arabic: bool = True


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
    unique: int = 0
    cached: int = 0
    pending: int = 0
    translated: int = 0
    accepted: int = 0
    rejected: int = 0
    qa_errors: int = 0
    stopped: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    failed: int = 0
    strategy: str = ""
    strategy_reasons: list[str] = field(default_factory=list)
    fallbacks: list[str] = field(default_factory=list)
    patch_files: list[str] = field(default_factory=list)
    runtime_files: list[str] = field(default_factory=list)
    runtime_pairs: int = 0
    manifest_path: str = ""
    report_path: str = ""
    report_html_path: str = ""
    workspace_root: str = ""
    warnings: list[str] = field(default_factory=list)


def choose_strategy(profile, levels: dict) -> tuple[str, list[str]]:
    """Static vs runtime decision with explanations (§9, no silent magic).

    CASES: IL2CPP → runtime (static text unreachable). Bundles present →
    runtime (rebuild unsupported — "static write-back unavailable; runtime
    overlay selected"). Parse AUTOMATIC on bundle-free Mono → static.
    Anything weaker → runtime (safer; static is attempted nowhere blind).
    """
    from almurrib.engine_adapters.unity.analysis import Backend

    if profile.backend is Backend.IL2CPP:
        return ("runtime", [
            "IL2CPP backend: native text is only safely reachable at runtime",
            "static IL2CPP analysis is detection-grade, never patch-grade",
        ])
    if profile.bundles:
        return ("runtime", [
            f"{len(profile.bundles)} asset bundle(s) present",
            "static write-back unavailable for bundles; runtime overlay selected",
            "single-asset patching stays available via export for experts",
        ])
    if levels.get(Capability.TEXT_ASSET) is Level.AUTOMATIC:
        return ("static", [
            "TextAsset/MonoBehaviour objects are directly writable",
            "no bundles block the rebuild path",
            "runtime bundle is still generated if static export fails",
        ])
    return ("runtime", [
        "parse capability is not AUTOMATIC — static patch would be a gamble",
        "runtime overlay selected as the safe default",
    ])


def suggest_fallbacks(profile, levels: dict,
                      error_kind: str = "") -> list[str]:
    """Visible fallback advice for known failures (§39, never silent)."""
    from almurrib.engine_adapters.unity.analysis import Backend

    tips = []
    if "parse" in error_kind or "readable" in error_kind:
        tips.append("UnityPy cannot parse this asset: open it in UABEA v8 "
                    "(external) to inspect, or rely on the runtime bundle.")
    if profile.bundles or "bundle" in error_kind:
        tips.append("AssetBundle rebuilds are unsupported in-process: use "
                    "UABEA v8 externally, or ship the XUnity runtime bundle.")
    if profile.backend is Backend.IL2CPP:
        tips.append("IL2CPP game: install BepInEx 6 + XUnity IL2CPP build "
                    "into the working copy for runtime translation.")
    if levels.get(Capability.TEXTMESHPRO) is not Level.UNSUPPORTED:
        tips.append("Arabic boxes in-game: set FallbackFontTextMeshPro in "
                    "Config.ini (TMP bundle must match the game version).")
    if not tips:
        tips.append("No specific fallback: see docs/UNITY_TROUBLESHOOTING.md "
                    "or file the exact error text.")
    return tips


def explain_entry(entry, profile=None, levels: dict | None = None) -> dict:
    """Per-entry diagnostics: 'why isn't this text Arabic?' (§21)."""
    ref = entry.source_refs[0] if entry.source_refs else None
    extra = ref.extra if ref is not None else {}
    statement = ref.statement if ref is not None else "?"
    method = {
        "sheet_entry": "language-sheet element",
        "text_asset": "TextAsset blob",
        "field": "MonoBehaviour typetree field",
        "name": "object name",
    }.get(statement, statement)
    qa = entry.qa_flags or []
    if entry.translated_text and not qa:
        translation = "SUCCESS"
    elif entry.translated_text:
        translation = f"FLAGGED ({len(qa)} QA flag(s))"
    elif entry.status.value == "failed":
        translation = "FAILED (provider)"
    else:
        translation = "PENDING (not translated yet)"
    tags = entry.tags or []
    if "sheet" in tags or statement in ("sheet_entry", "text_asset"):
        writeback = ("STATIC where the asset rebuilds; "
                     "RUNTIME overlay otherwise (bundles)")
    elif statement == "field":
        writeback = "STATIC where UnityPy rebuilds the asset"
    else:
        writeback = "UNKNOWN — see fallback"
    return {
        "source": entry.source_text,
        "location": (f"{ref.file}:{ref.line}" if ref is not None else "?"),
        "asset_class": extra.get("class", "?"),
        "field": extra.get("field", "?"),
        "extraction_method": method,
        "candidate_class": (entry.metadata or {}).get("candidate_class", "?"),
        "translation": translation,
        "qa_flags": qa,
        "write_back": writeback,
        "fallback": ("Runtime overlay" if "RUNTIME" in writeback or "bundle"
                     in writeback.lower() else "Static patch"),
    }


def localize_unity_game(game_dir: Path, *, db, provider,
                        options: UnityLocalizeOptions | None = None,
                        progress=None, log=None,
                        stop_event=None, pause_event=None
                        ) -> UnityLocalizeReport:
    """Run the full Unity flow. See module docstring for the contract."""
    from almurrib.core.pipeline import LocalizationPipeline
    from almurrib.core.workflow import (
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

    emit("[1/8] Detecting Unity...")
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

    emit("[2/8] Preparing safe workspace (backup + manifest)...")
    workspace_dir = options.workspace_dir or \
        game_dir.parent / f"{game_dir.name}_ar_work"
    from almurrib.core.errors import ExportError as _ExportError

    try:
        workspace = prepare_workspace(game_dir, workspace_dir)
    except _ExportError:
        resumed = resume_workspace(workspace_dir,
                                   game_identity(game_dir.resolve()))
        if resumed is None:
            raise
        workspace = resumed
        emit("[2/8] Reusing complete workspace from a previous run "
             f"({len(workspace.files)} files verified present).")
    report.game_id = workspace.game_id
    report.workspace_root = str(workspace.root)

    emit("[3/8] Scanning assets...")
    pipeline = LocalizationPipeline(adapters=default_adapters())
    emit("[4/8] Extracting text...")
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
    report.unique = len({e.fingerprint for e in entries})
    emit(f"[5/8] Preparing translation: {len(entries)} entries, "
         f"{report.unique} unique...")

    emit(f"[6/8] Translating {len(entries)} entries...")
    stats = translate_entries(
        entries, db, provider, source_lang=options.source_lang,
        target_lang=options.target_lang, project_id=project_id,
        force=options.force, reuse_machine_tm=options.reuse_machine_tm,
        log=log, stop_event=stop_event, pause_event=pause_event)
    report.cached = stats.cache_hits + stats.memory_hits
    # translated == accepted-and-clean occurrences (dedup fan-out counts
    # every occurrence, not just representatives — §40 honesty).
    report.translated = stats.accepted
    report.pending = sum(1 for e in entries if not e.translated_text)
    report.failed = stats.failed
    report.accepted = stats.accepted
    report.rejected = stats.rejected
    report.tokens_in = stats.input_tokens
    report.tokens_out = stats.output_tokens
    report.qa_errors = stats.arabic_errors + stats.placeholder_failures
    report.stopped = stats.stopped

    strategy = options.strategy
    if strategy == "auto":
        strategy, strategy_reasons = choose_strategy(profile, levels)
    else:
        strategy_reasons = [f"user-selected strategy: {strategy}"]
    report.strategy = strategy
    report.strategy_reasons = strategy_reasons
    for reason in strategy_reasons:
        emit(f"[STRATEGY] {reason}")

    repo = EntryRepository(db)
    stored = [e for e in repo.list(project_id=project_id)
              if e.translated_text
              and e.status is not EntryStatus.OBSOLETE]

    if strategy == "static":
        emit("[7/8] Building patch (static)...")
        try:
            written = export_for_engine(
                EngineType.UNITY, game_dir, db,
                output_dir=workspace.root / "patch",
                target_lang=options.target_lang, project_id=project_id,
                visual_arabic=options.visual_arabic)
            report.patch_files = [str(p) for p in written]
            record_modified(
                workspace,
                [str(Path(p).relative_to(workspace.root)) for p in written
                 if _is_relative(p, workspace.root)])
        except Exception as exc:
            report.warnings.append(f"static patch failed ({exc}); "
                                   "runtime bundle produced as fallback.")
            report.strategy = "static+runtime-fallback"
            report.fallbacks = suggest_fallbacks(profile, levels, str(exc))
    if report.strategy != "static" or not report.patch_files:
        emit("[7/8] Building patch (runtime bundle)...")
        bundle = generate_xunity_bundle(
            stored, workspace.root / "XUnity_AR",
            lang=options.target_lang, from_lang=options.source_lang,
            visual_arabic=options.visual_arabic)
        report.runtime_files = bundle.files
        report.runtime_pairs = bundle.pairs
        if bundle.skipped_long:
            report.warnings.append(
                f"{bundle.skipped_long} entries exceed XUnity's 2500-char "
                "limit and were skipped from the runtime bundle.")

    emit("[8/8] Verifying (originals, patch, manifest)...")
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
        "tool": "UnityPy",
        "tool_version": _tool_version("UnityPy"),
        "why_selected": report.strategy_reasons,
        "fallback_if_failed": ("UABEA v8 externally, or the XUnity runtime "
                               "bundle in this workspace"),
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
        "fallbacks": report.fallbacks,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    report.manifest_path = str(manifest_path)
    report_path, html_path = write_unity_report(
        report, profile, workspace, provider)
    report.report_path = str(report_path)
    report.report_html_path = str(html_path)
    emit(f"[8/8] Report: {report_path.name}")
    return report


def write_unity_report(report: UnityLocalizeReport, profile,
                       workspace, provider) -> tuple[Path, Path]:
    """Full localization report: JSON + readable HTML (§42).

    Numbers are exact pipeline counts — never "translated" unless
    accepted/persisted (§40).
    """
    from almurrib.engine_adapters.unity import analysis as _analysis

    identity = getattr(getattr(provider, "config", None), "identity", "?")
    data = {
        "game": str(profile.game_dir),
        "game_id": report.game_id,
        "unity_version": profile.unity_version,
        "version_confidence": profile.version_confidence,
        "backend": profile.backend.value,
        "arch": profile.arch,
        "capabilities": _analysis.capability_summary(profile),
        "evidence": profile.evidence,
        "tool": "UnityPy",
        "tool_version": _tool_version("UnityPy"),
        "extracted": report.extracted,
        "unique": report.unique,
        "cached": report.cached,
        "pending": report.pending,
        "translated": report.translated,
        "accepted": report.accepted,
        "rejected": report.rejected,
        "qa_errors": report.qa_errors,
        "stopped": report.stopped,
        "failed": report.failed,
        "tokens_in": report.tokens_in,
        "tokens_out": report.tokens_out,
        "strategy": report.strategy,
        "strategy_reasons": report.strategy_reasons,
        "statically_written": len(report.patch_files),
        "runtime_pairs": report.runtime_pairs,
        "unresolved": report.pending,
        "provider": identity,
        "warnings": report.warnings,
        "fallbacks": report.fallbacks,
        "workspace": report.workspace_root,
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    root = workspace.root
    json_path = root / "unity_localization_report.json"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    rows = "\n".join(
        f"<tr><td>{k}</td><td>{v if not isinstance(v, list) else '<br>'.join(map(str, v)) or '—'}</td></tr>"
        for k, v in data.items() if k != "capabilities" and k != "evidence")
    caps = "<br>".join(data["capabilities"])
    html_path = root / "unity_localization_report.html"
    html_path.write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<title>Almurrib Unity report — {report.game_id}</title></head>"
        "<body><h1>Unity localization report</h1>"
        "<table border='1' cellpadding='4'>"
        f"{rows}"
        f"<tr><td>capabilities</td><td>{caps}</td></tr>"
        f"<tr><td>evidence</td><td>{'<br>'.join(data['evidence'])}</td></tr>"
        "</table></body></html>", encoding="utf-8")
    return json_path, html_path


def _tool_version(name: str) -> str:
    """Best-effort installed tool version (never raises, never secrets)."""
    try:
        module = __import__(name)
        return str(getattr(module, "__version__", "?"))
    except Exception:
        return "not installed"


def _is_relative(path, root) -> bool:
    try:
        Path(path).relative_to(root)
        return True
    except ValueError:
        return False
