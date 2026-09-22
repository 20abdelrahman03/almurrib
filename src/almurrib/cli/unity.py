"""``almurrib unity`` command group (§33 of the milestone).

Thin edge over shared services: structured detection, asset inspection,
extraction (delegated), one-click localize (the Unity service), tool
status, runtime-bundle generation and workspace launch. No workflow
logic lives here — CLI and GUI both call the same service functions.

Old top-level commands are untouched; this group only ADDS Unity depth::

    almurrib unity detect   <game>
    almurrib unity inspect  <game> [--max-assets N]
    almurrib unity extract  <game> [--db ...] [--json ...] [--project ...]
    almurrib unity localize <game> [--db ...] [--provider ...] [--strategy ...]
    almurrib unity tools    [game]
    almurrib unity runtime  <game> [--db ...] [--out ...]
    almurrib unity run      <workspace>
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

    p = u.add_parser("run", help="launch a localized workspace copy")
    p.add_argument("workspace", type=Path)


def cmd_unity(args: argparse.Namespace) -> int:
    command = getattr(args, "unity_command", None)
    if command is None:
        print("usage: almurrib unity {detect|inspect|extract|localize|"
              "tools|runtime|run}", file=sys.stderr)
        return 2
    handler = {"detect": _detect, "inspect": _inspect, "extract": _extract,
               "localize": _localize, "tools": _tools, "runtime": _runtime,
               "run": _run}[command]
    return handler(args)


def _detect(args) -> int:
    from almurrib.engine_adapters.unity import analysis as A

    profile = A.analyze_game(args.game_dir)
    print(f"game            : {args.game_dir}")
    print(f"unity version   : {profile.unity_version or 'unknown'}")
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
    print(f"extracted       : {report.extracted}")
    print(f"translated      : {report.translated} (failed: {report.failed})")
    print(f"strategy        : {report.strategy or 'none'}")
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
