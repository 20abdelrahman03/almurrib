"""almurrib CLI — the developer-facing working path.

Commands (Phase 1 first half):

    almurrib detect   <game_dir>                     # which engine is this?
    almurrib extract  <game_dir> [--db ...] [--json ...]   # extract + store
    almurrib inspect  --db ... [--status ...] [--limit N]  # view entries
    almurrib db       --db ...                       # database summary

Exact flags are intentionally plain argparse — no framework dependency.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from almurrib.core.errors import AlMurribError
from almurrib.core.model import EntryStatus
from almurrib.core.pipeline import LocalizationPipeline, PipelineContext
from almurrib.engine_adapters import default_adapters
from almurrib.engine_adapters.renpy.exporter import export_json
from almurrib.storage.database import Database
from almurrib.storage.repository import EntryRepository

DEFAULT_DB = Path("almurrib.db")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="almurrib",
        description="المعرب — Arabic game localization ecosystem (Phase 1 foundation)",
    )
    parser.add_argument("--version", action="store_true", help="print version and exit")
    sub = parser.add_subparsers(dest="command")

    p_detect = sub.add_parser("detect", help="detect the game engine for a directory")
    p_detect.add_argument("game_dir", type=Path)

    p_extract = sub.add_parser(
        "extract", help="extract translatable text into SQLite (+ optional JSON export)"
    )
    p_extract.add_argument("game_dir", type=Path)
    p_extract.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path")
    p_extract.add_argument("--json", type=Path, default=None, help="also export entries to JSON")
    p_extract.add_argument("--project", type=str, default=None, help="project name (default: dir name)")
    p_extract.add_argument("--target-lang", type=str, default="ar")

    p_inspect = sub.add_parser("inspect", help="inspect stored localization entries")
    p_inspect.add_argument("--db", type=Path, default=DEFAULT_DB)
    p_inspect.add_argument("--status", type=str, default=None,
                           choices=[s.value for s in EntryStatus])
    p_inspect.add_argument("--limit", type=int, default=20)
    p_inspect.add_argument("--json", action="store_true", help="emit JSON instead of a table")

    p_db = sub.add_parser("db", help="show database summary")
    p_db.add_argument("--db", type=Path, default=DEFAULT_DB)

    p_translate = sub.add_parser(
        "translate", help="translate stored entries via the configured provider"
    )
    p_translate.add_argument("--db", type=Path, default=DEFAULT_DB)
    p_translate.add_argument("--source-lang", type=str, default=None)
    p_translate.add_argument("--target-lang", type=str, default=None)
    p_translate.add_argument("--force", action="store_true",
                             help="retranslate even already-translated entries")

    p_export = sub.add_parser(
        "export", help="generate Ren'Py localization files from stored translations"
    )
    p_export.add_argument("game_dir", type=Path)
    p_export.add_argument("--db", type=Path, default=DEFAULT_DB)
    p_export.add_argument("--out", type=Path, default=None, help="output dir (patch)")
    p_export.add_argument("--target-lang", type=str, default=None)

    p_localize = sub.add_parser(
        "localize", help="full workflow: detect → extract → translate → export"
    )
    p_localize.add_argument("game_dir", type=Path)
    p_localize.add_argument("--db", type=Path, default=DEFAULT_DB)
    p_localize.add_argument("--out", type=Path, default=None)
    p_localize.add_argument("--project", type=str, default=None)
    p_localize.add_argument("--source-lang", type=str, default=None)
    p_localize.add_argument("--target-lang", type=str, default=None)
    p_localize.add_argument("--force", action="store_true")

    return parser


def _pipeline() -> LocalizationPipeline:
    return LocalizationPipeline(adapters=default_adapters())


def _cmd_detect(args: argparse.Namespace) -> int:
    pipeline = _pipeline()
    adapter = pipeline.detect_engine(args.game_dir)
    result = adapter.detect(args.game_dir)
    print(f"engine     : {result.engine.value}")
    print(f"confidence : {result.confidence:.2f}")
    for reason in result.reasons:
        print(f"  - {reason}")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    pipeline = _pipeline()
    context = PipelineContext(game_dir=args.game_dir, target_lang=args.target_lang)
    result = pipeline.extract(args.game_dir, context)

    with Database(args.db) as db:
        repo = EntryRepository(db)
        engine = pipeline.detect_engine(args.game_dir).engine_type
        project_name = args.project or args.game_dir.resolve().name
        project = repo.ensure_project(project_name, str(args.game_dir.resolve()), engine)
        stored = repo.upsert_many(project.id, result.entries)

    if args.json:
        export_json(result.entries, args.json)

    print(f"engine        : {engine.value}")
    print(f"files scanned : {result.files_scanned}")
    print(f"entries       : {len(result.entries)} extracted, {stored} stored")
    print(f"database      : {args.db}")
    if args.json:
        print(f"json export   : {args.json}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        repo = EntryRepository(db)
        status = EntryStatus(args.status) if args.status else None
        entries = repo.list(status=status, limit=args.limit)
        if args.json:
            print(json.dumps([e.to_dict() for e in entries], ensure_ascii=False, indent=2))
            return 0
        if not entries:
            print("(no entries stored)")
            return 0
        for e in entries:
            ref = e.source_refs[0] if e.source_refs else None
            where = f"{ref.file}:{ref.line}" if ref else "?"
            speaker = f"[{e.speaker}] " if e.speaker else ""
            print(f"{e.id[:10]}  {e.status.value:12}  {where:28}  {speaker}{e.source_text}")
    return 0


def _cmd_db(args: argparse.Namespace) -> int:
    with Database(args.db) as db:
        repo = EntryRepository(db)
        print(f"database       : {args.db}")
        print(f"schema version : {db.schema_version()}")
        print(f"entries        : {repo.count()}")
        for status in EntryStatus:
            count = len(repo.list(status=status))
            if count:
                print(f"  {status.value:12}: {count}")
    return 0


def _settings(args: argparse.Namespace):
    from almurrib.core.config import load_settings

    overrides: dict[str, str] = {}
    if getattr(args, "db", None) is not None:
        overrides["ALMURRIB_DATABASE"] = str(args.db)
    for arg_name, key in (("source_lang", "ALMURRIB_SOURCE_LANG"),
                          ("target_lang", "ALMURRIB_TARGET_LANG"),
                          ("out", "ALMURRIB_OUTPUT_DIR")):
        value = getattr(args, arg_name, None)
        if value is not None:
            overrides[key] = str(value)
    return load_settings(overrides=overrides)


def _build_provider(settings):
    from almurrib.providers import build_provider

    return build_provider(settings.provider_config())


def _print_stats(stats) -> None:
    print(f"  already translated : {stats.already_translated}")
    print(f"  memory hits        : {stats.memory_hits}")
    print(f"  cache hits         : {stats.cache_hits}")
    print(f"  api batches        : {stats.api_calls}")
    print(f"  api translations   : {stats.api_translated}")
    if stats.placeholder_failures:
        print(f"  placeholder issues : {stats.placeholder_failures} (flagged)")
    if stats.failed:
        print(f"  failed             : {stats.failed}")
        for err in stats.errors[:3]:
            print(f"    ! {err}")


def _cmd_translate(args: argparse.Namespace) -> int:
    settings = _settings(args)
    provider = _build_provider(settings)
    print(f"provider      : {provider.config.identity}")
    print(f"endpoint      : {provider.config.base_url}  (external API)")
    with Database(settings.database_path) as db:
        from almurrib.core.workflow import translate_entries

        repo = EntryRepository(db)
        entries = repo.list()
        if not entries:
            print("(no entries stored — run 'extract' first)")
            return 0
        stats = translate_entries(
            entries, db, provider,
            source_lang=settings.source_lang, target_lang=settings.target_lang,
        )
        repo.upsert_for_entries(entries)
    print(f"entries       : {stats.total}")
    _print_stats(stats)
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    settings = _settings(args)
    pipeline = _pipeline()
    with Database(settings.database_path) as db:
        from almurrib.core.workflow import export_translations

        written = export_translations(
            pipeline, args.game_dir, db,
            output_dir=settings.output_dir, target_lang=settings.target_lang,
        )
    print(f"exported {len(written)} file(s):")
    for path in written:
        print(f"  {path}")
    print("original game files were NOT modified.")
    return 0


def _cmd_localize(args: argparse.Namespace) -> int:
    settings = _settings(args)
    pipeline = _pipeline()
    provider = _build_provider(settings)
    from almurrib.core.workflow import (
        export_translations,
        extract_and_store,
        translate_entries,
    )

    print(f"game          : {args.game_dir}")
    print(f"provider      : {provider.config.identity}")
    print(f"endpoint      : {provider.config.base_url}  (external API)")
    with Database(settings.database_path) as db:
        entries, project_id = extract_and_store(
            pipeline, args.game_dir, db,
            target_lang=settings.target_lang, project_name=args.project,
        )
        print(f"entries       : {len(entries)} extracted")
        stats = translate_entries(
            entries, db, provider,
            source_lang=settings.source_lang, target_lang=settings.target_lang,
            project_id=project_id, force=args.force,
        )
        _print_stats(stats)
        written = export_translations(
            pipeline, args.game_dir, db,
            output_dir=settings.output_dir, target_lang=settings.target_lang,
        )
    print(f"output        : {settings.output_dir} ({len(written)} file(s))")
    print("original game files were NOT modified.")
    return 0


_COMMANDS = {
    "detect": _cmd_detect,
    "extract": _cmd_extract,
    "inspect": _cmd_inspect,
    "db": _cmd_db,
    "translate": _cmd_translate,
    "export": _cmd_export,
    "localize": _cmd_localize,
}


def main(argv: list[str] | None = None) -> int:
    from almurrib import __version__

    parser = _build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False):
        print(f"almurrib {__version__}")
        return 0
    if args.command is None:
        parser.print_help()
        return 0
    handler = _COMMANDS[args.command]
    try:
        return handler(args)
    except AlMurribError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
