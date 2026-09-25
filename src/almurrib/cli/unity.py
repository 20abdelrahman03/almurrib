"""``almurrib unity`` command group (§33 of the milestone).

Thin edge over shared services: structured detection, asset inspection,
extraction (delegated), one-click localize (the Unity service), tool
status, runtime-bundle generation and workspace launch. No workflow
logic lives here — CLI and GUI both call the same service functions.

Old top-level commands are untouched; this group only ADDS Unity depth::

    almurrib unity detect    <game>
    almurrib unity inspect   <game> [--max-assets N]
    almurrib unity scan      <game>   (detect + extract + dedup counts)
    almurrib unity extract   <game> [--db ...] [--json ...] [--project ...]
    almurrib unity preflight <game> [--db ...]   (counts + estimate + canary)
    almurrib unity localize  <game> [--db ...] [--provider ...] [--strategy ...]
    almurrib unity verify    <workspace>   (re-parse patch files)
    almurrib unity rollback  <workspace>   (verify originals + discard copy)
    almurrib unity explain   --db ... --contains TEXT   (why not translated?)
    almurrib unity tools     [game]
    almurrib unity runtime   <game> [--db ...] [--out ...]
    almurrib unity run       <workspace>
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def register_unity(subparsers) -> None:
    p_unity = subparsers.add_parser("unity", help="Unity game workflow")
    u = p_unity.add_subparsers(dest="unity_command")

    p = u.add_parser("detect", help="structured Unity profile + capabilities")
    p.add_argument("game_dir", type=Path)

    p = u.add_parser("inspect", help="profile + per-asset census")
    p.add_argument("game_dir", type=Path)
    p.add_argument("--max-assets", type=int, default=200)

    p = u.add_parser("scan", help="detect + extract + dedup counts (no translate)")
    p.add_argument("game_dir", type=Path)
    p.add_argument("--db", type=Path, default=Path("almurrib.db"))
    p.add_argument("--project", type=str, default=None)

    p = u.add_parser("preflight",
                     help="extract if needed, then counts + token estimate + "
                          "canary (never translates)")
    p.add_argument("game_dir", type=Path)
    p.add_argument("--db", type=Path, default=Path("almurrib.db"))
    p.add_argument("--provider", type=str, default=None)
    p.add_argument("--model", type=str, default=None)
    p.add_argument("--base-url", type=str, default=None)

    p = u.add_parser("extract", help="extract Unity text into SQLite")
    p.add_argument("game_dir", type=Path)
    p.add_argument("--db", type=Path, default=Path("almurrib.db"))
    p.add_argument("--json", type=Path, default=None)
    p.add_argument("--project", type=str, default=None)
    p.add_argument("--target-lang", type=str, default="ar")

    p = u.add_parser("localize", help="one-click Unity localize (service)")
    p.add_argument("game_dir", type=Path)
    p.add_argument("--db", type=Path, default=Path("almurrib.db"))
    p.add_argument("--project", type=str, default=None)
    p.add_argument("--source-lang", type=str, default=None)
    p.add_argument("--target-lang", type=str, default=None)
    p.add_argument("--provider", type=str, default=None)
    p.add_argument("--model", type=str, default=None)
    p.add_argument("--base-url", type=str, default=None)
    p.add_argument("--strategy", type=str, default="auto",
                   choices=["auto", "static", "runtime"])
    p.add_argument("--workspace", type=Path, default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--reuse-machine-tm", action="store_true")

    p = u.add_parser("tools", help="external Unity tool status")
    p.add_argument("game_dir", type=Path, nargs="?")

    p = u.add_parser("runtime", help="XUnity bundle from stored translations")
    p.add_argument("game_dir", type=Path)
    p.add_argument("--db", type=Path, default=Path("almurrib.db"))
    p.add_argument("--out", type=Path, default=None)

    p = u.add_parser("verify", help="re-parse workspace patch files")
    p.add_argument("workspace", type=Path)

    p = u.add_parser("rollback", help="verify originals + discard workspace")
    p.add_argument("workspace", type=Path)

    p = u.add_parser("explain", help="why isn't this text translated?")
    p.add_argument("--db", type=Path, default=Path("almurrib.db"))
    p.add_argument("--game-dir", type=Path, default=None)
    p.add_argument("--contains", type=str, required=True)
    p.add_argument("--limit", type=int, default=5)

    p = u.add_parser("run", help="launch a localized workspace copy")
    p.add_argument("workspace", type=Path)


def cmd_unity(args: argparse.Namespace) -> int:
    command = getattr(args, "unity_command", None)
    if command is None:
        print("usage: almurrib unity {detect|inspect|scan|extract|preflight|"
              "localize|verify|rollback|explain|tools|runtime|run}",
              file=sys.stderr)
        return 2
    handler = {"detect": _detect, "inspect": _inspect, "extract": _extract,
               "scan": _scan, "preflight": _preflight, "verify": _verify,
               "rollback": _rollback, "explain": _explain,
               "localize": _localize, "tools": _tools, "runtime": _runtime,
               "run": _run}[command]
    return handler(args)


def _detect(args) -> int:
    from almurrib.engine_adapters.unity import analysis as A

    profile = A.analyze_game(args.game_dir)
    print(f"game            : {args.game_dir}")
    print(f"version         : {A.version_label(profile)}")
    print(f"executable      : {profile.executable or 'not found'}")
    print(f"backend         : {profile.backend.value}")
    print(f"arch            : {profile.arch or 'unknown'}")
    print(f"data dirs       : {', '.join(profile.data_dirs) or 'none'}")
    print(f"serialized      : {profile.serialized_assets} asset(s)")
    print(f"bundles         : {len(profile.bundles)}")
    for bit in ("streaming_assets", "addressables", "localization_package",
                "textmeshpro", "legacy_ui", "bepinex", "melonloader"):
        if getattr(profile, bit):
            print(f"feature         : {bit}")
    print("capabilities    :")
    for line in A.capability_summary(profile):
        print(f"  {line}")
    return 0


def _inspect(args) -> int:
    from almurrib.engine_adapters.unity import UnityAdapter
    from almurrib.engine_adapters.unity.unityfs import inspect_asset

    _detect(args)
    assets = UnityAdapter._find_assets(Path(args.game_dir).resolve())
    print(f"assets          : {len(assets)} file(s)")
    shown = 0
    for asset in assets[:args.max_assets]:
        report = inspect_asset(asset)
        if report.loadable:
            kinds = ",".join(f"{k}:{v}"
                             for k, v in sorted((report.classes or {}).items()))
            print(f"  ✓ {asset.name} ({report.object_count} objects: {kinds})")
        else:
            print(f"  ✗ {asset.name}: {report.error}")
        shown += 1
    if len(assets) > shown:
        print(f"  ... and {len(assets) - shown} more (use --max-assets)")
    return 0


def _extract(args) -> int:
    from almurrib.cli.main import _cmd_extract

    return _cmd_extract(args)


def _localize(args) -> int:
    from almurrib.cli.main import _build_provider, _settings
    from almurrib.engine_adapters.unity.service import (
        UnityLocalizeOptions,
        localize_unity_game,
    )
    from almurrib.storage.database import Database

    settings = _settings(args)
    provider = _build_provider(settings)
    options = UnityLocalizeOptions(
        target_lang=settings.target_lang, source_lang=settings.source_lang,
        project_name=args.project, workspace_dir=args.workspace,
        strategy=args.strategy, force=args.force,
        reuse_machine_tm=settings.reuse_machine_tm)
    with Database(settings.database_path) as db:
        report = localize_unity_game(
            args.game_dir, db=db, provider=provider, options=options,
            progress=print, log=print)
    print(f"game id         : {report.game_id or 'n/a'}")
    print(f"unity           : {report.unity_version or 'unknown'} "
          f"/ {report.backend}")
    print(f"extracted       : {report.extracted} "
          f"(unique: {report.unique}, cached: {report.cached}, "
          f"pending: {report.pending})")
    print(f"translated      : {report.translated} "
          f"(accepted: {report.accepted}, rejected: {report.rejected}, "
          f"failed: {report.failed}, tokens {report.tokens_in}/"
          f"{report.tokens_out})")
    print(f"strategy        : {report.strategy or 'none'}")
    for reason in report.strategy_reasons:
        print(f"  why: {reason}")
    for tip in report.fallbacks:
        print(f"  fallback: {tip}")
    if report.report_path:
        print(f"report          : {report.report_path}")
        print(f"report html     : {report.report_html_path}")
    for path in report.patch_files:
        print(f"  patch: {path}")
    for name in report.runtime_files:
        print(f"  runtime: {name} ({report.runtime_pairs} pairs)")
    for warning in report.warnings:
        print(f"warning         : {warning}")
    print(f"manifest        : {report.manifest_path or 'n/a'}")
    print(f"workspace       : {report.workspace_root or 'n/a'}")
    print(report.support_note)
    print("original game files were NOT modified.")
    return 1 if report.failed else 0


def _tools(args) -> int:
    from almurrib.engine_adapters.unity.tools import status_table

    for line in status_table(getattr(args, "game_dir", None)):
        print(line)
    return 0


def _runtime(args) -> int:
    from almurrib.core.workflow import resolve_project
    from almurrib.engine_adapters.unity.runtime import generate_xunity_bundle
    from almurrib.storage.database import Database
    from almurrib.storage.repository import EntryRepository

    out = args.out or Path(f"{Path(args.game_dir).name}_XUnity_AR")
    with Database(args.db) as db:
        project = resolve_project(db, args.game_dir)
        entries = EntryRepository(db).list(
            project_id=project.id if project else None)
    bundle = generate_xunity_bundle(entries, out)
    print(f"pairs           : {bundle.pairs}")
    print(f"skipped (long)  : {bundle.skipped_long}")
    print(f"skipped (empty) : {bundle.skipped_empty}")
    print(f"duplicates      : {bundle.duplicate_sources}")
    for name in bundle.files:
        print(f"  {name}")
    return 0


def _run(args) -> int:
    root = Path(args.workspace).resolve()
    if not root.is_dir():
        print(f"error: workspace not found: '{args.workspace}'",
              file=sys.stderr)
        return 2
    exes = sorted(root.glob("*.exe"))
    if not exes:
        print("error: no game exe in workspace root", file=sys.stderr)
        return 2
    print(f"launching       : {exes[0].name}")
    try:
        if sys.platform == "win32":
            subprocess.Popen([str(exes[0])], cwd=str(root),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen([str(exes[0])], cwd=str(root))
    except OSError as exc:
        print(f"error: cannot launch ({exc})", file=sys.stderr)
        return 2
    return 0


def _scan(args) -> int:
    """Detect + extract + dedup counts. No provider calls, no translation."""
    from almurrib.core.pipeline import LocalizationPipeline
    from almurrib.core.workflow import extract_and_store
    from almurrib.engine_adapters.registry import default_adapters
    from almurrib.storage.database import Database

    _detect(args)
    pipeline = LocalizationPipeline(adapters=default_adapters())
    with Database(args.db) as db:
        entries, _ = extract_and_store(
            pipeline, args.game_dir, db, project_name=args.project)
    unique = len({e.fingerprint for e in entries})
    print(f"extracted       : {len(entries)}")
    print(f"unique strings  : {unique}")
    print(f"duplicate occurrences: {len(entries) - unique}")
    return 0


def _preflight(args) -> int:
    """Counts + measured token estimate + canary. Never translates."""
    from almurrib.cli.main import _build_provider, _settings
    from almurrib.core.workflow import (
        dry_run_report,
        extract_and_store,
        resolve_project,
    )
    from almurrib.core.pipeline import LocalizationPipeline
    from almurrib.engine_adapters.registry import default_adapters
    from almurrib.storage.database import Database
    from almurrib.storage.repository import EntryRepository

    settings = _settings(args)
    provider = _build_provider(settings)
    pipeline = LocalizationPipeline(adapters=default_adapters())
    with Database(settings.database_path) as db:
        project = resolve_project(db, args.game_dir)
        if project is None:
            entries, project_id = extract_and_store(
                pipeline, args.game_dir, db)
        else:
            project_id = project.id
            entries = EntryRepository(db).list(project_id=project_id)
        estimate = dry_run_report(
            entries, db, provider,
            source_lang=settings.source_lang,
            target_lang=settings.target_lang,
            project_id=project_id, log=print)
    canary = estimate.canary
    print(f"canary          : {'PASS' if canary and canary.passed else 'FAIL'}")
    return 0 if canary and canary.passed else 2


def _verify(args) -> int:
    """Re-parse every patch file inside a workspace (§31 validation)."""
    from almurrib.engine_adapters.unity.unityfs import validate_patch
    from almurrib.engine_adapters.unity.workspace import load_workspace

    try:
        workspace = load_workspace(args.workspace)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    patch_files = sorted((workspace.root / "patch").rglob("*"))
    patch_files = [p for p in patch_files if p.is_file()]
    if not patch_files:
        print("no patch files in workspace (runtime-only or empty run)")
        return 0
    failed = 0
    for path in patch_files:
        try:
            count = validate_patch(path)
            print(f"  ✓ {path.name} ({count} objects)")
        except Exception as exc:
            print(f"  ✗ {path.name}: {exc}")
            failed += 1
    print(f"verified        : {len(patch_files) - failed}/{len(patch_files)}")
    return 1 if failed else 0


def _rollback(args) -> int:
    """One-action rollback: verify originals, discard the copy (§32)."""
    from almurrib.engine_adapters.unity.workspace import rollback_workspace

    try:
        problems = rollback_workspace(args.workspace)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if problems:
        print("workspace removed, BUT the sources looked different:")
        for problem in problems:
            print(f"  ! {problem}")
        return 1
    print("workspace removed; original game verified untouched.")
    return 0


def _explain(args) -> int:
    """Per-entry diagnostics: why isn't this text translated? (§21)."""
    from almurrib.core.workflow import resolve_project
    from almurrib.engine_adapters.unity.service import explain_entry
    from almurrib.storage.database import Database
    from almurrib.storage.repository import EntryRepository

    with Database(args.db) as db:
        project = None
        if args.game_dir is not None:
            project = resolve_project(db, args.game_dir)
        entries = EntryRepository(db).list(
            project_id=project.id if project else None)
    needle = args.contains.lower()
    shown = 0
    for entry in entries:
        if needle not in entry.source_text.lower():
            continue
        report = explain_entry(entry)
        print(f"--- {report['location']}")
        for key in ("source", "asset_class", "field", "extraction_method",
                    "candidate_class", "translation", "qa_flags",
                    "write_back", "fallback"):
            print(f"  {key}: {report[key]}")
        shown += 1
        if shown >= args.limit:
            break
    if not shown:
        print("no stored entries contain that text")
        return 1
    return 0
