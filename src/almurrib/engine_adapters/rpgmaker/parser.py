"""RPG Maker MV/MZ data parser (JSON walk, conservative).

Reads the plain-JSON data files both versions ship:

* MV: ``www/data/*.json`` — MZ: ``data/*.json`` (auto-detected).
* Map files (``MapNNN.json``): event command lists — Show Text (401),
  Show Choices (102). Other codes (conditions, variables, JS plugins)
  are deliberately skipped (see module docstring limits).
* Database files: actors/items/skills/... names, descriptions, profiles,
  terms; ``System.json`` title + terms; ``MapInfos.json`` map names.

Output is shared :class:`~almurrib.engine_adapters.raw.RawStatement`
records carrying a ``json_path`` (key/index navigation from the file root)
so write-back is exact. Malformed JSON raises ExtractionError with the
file name — never a bare traceback.
"""

from __future__ import annotations

import json
from pathlib import Path

from almurrib.core.errors import ExtractionError
from almurrib.engine_adapters.raw import RawStatement

# Event-command codes we extract (RPG Maker MV/MZ event list format).
CODE_SHOW_TEXT = 101  # header only (face/background); text follows in 401s
CODE_TEXT_LINE = 401  # one dialogue line
CODE_SHOW_CHOICES = 102  # parameters[0] = list of choice strings


def find_data_dir(game_dir: Path) -> tuple[Path, str] | None:
    """Locate the data directory. Returns (path, variant) or None."""
    mv_data = game_dir / "www" / "data"
    if mv_data.is_dir() and (mv_data / "System.json").is_file():
        return mv_data, "MV"
    mz_data = game_dir / "data"
    if mz_data.is_dir() and (mz_data / "System.json").is_file():
        return mz_data, "MZ"
    return None


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExtractionError(f"RPG Maker data file missing: '{path}'") from exc
    except (OSError, ValueError) as exc:
        raise ExtractionError(
            f"could not read RPG Maker data '{path}': {exc}",
            hint="data files must be valid UTF-8 JSON.",
        ) from exc


class _Collector:
    """Deterministic statement builder with per-file ordinal lines."""

    def __init__(self, rel: str) -> None:
        self.rel = rel
        self.statements: list[RawStatement] = []
        self.ordinal = 0

    def add(self, kind: str, text: str, *, speaker: str | None = None,
            speaker_var: str | None = None, json_path: list | None = None,
            translation: str | None = None) -> None:
        if not isinstance(text, str) or not text.strip():
            return
        self.ordinal += 1
        extra = {}
        if json_path is not None:
            extra["json_path"] = json.dumps(json_path, ensure_ascii=False)
        self.statements.append(RawStatement(
            kind=kind, text=text, file=self.rel, line=self.ordinal,
            speaker=speaker, speaker_var=speaker_var,
            translation=translation, extra=extra))


def _walk_commands(out: _Collector, commands: object, base_path: list,
                   speaker: str | None) -> None:
    if not isinstance(commands, list):
        return
    for index, command in enumerate(commands):
        if not isinstance(command, dict):
            continue
        code = command.get("code")
        params = command.get("parameters") or []
        path = [*base_path, index]
        if code == CODE_TEXT_LINE and params:
            out.add("say", str(params[0]), speaker=speaker,
                    speaker_var=speaker,
                    json_path=[*path, "parameters", 0])
        elif code == CODE_SHOW_CHOICES and params and isinstance(params[0], list):
            for choice_index, choice in enumerate(params[0]):
                out.add("menu_choice", str(choice), speaker=None,
                        json_path=[*path, "parameters", 0, choice_index])


def _parse_map(out: _Collector, data: object) -> None:
    if isinstance(data, dict) and data.get("displayName"):
        out.add("name", str(data["displayName"]),
                json_path=["displayName"])
    events = data.get("events") if isinstance(data, dict) else None
    if not isinstance(events, list):
        return
    for event_index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        name = event.get("name") if isinstance(event.get("name"), str) else None
        if name:
            out.add("name", name,
                    json_path=["events", event_index, "name"])
        pages = event.get("pages")
        if not isinstance(pages, list):
            continue
        for page_index, page in enumerate(pages):
            if not isinstance(page, dict):
                continue
            _walk_commands(out, page.get("list"),
                           ["events", event_index, "pages", page_index, "list"],
                           speaker=name)


def _parse_table(out: _Collector, data: object, fields: dict[str, str]) -> None:
    """Database arrays: [{name, description, ...}] with index-0 nulls."""
    if not isinstance(data, list):
        return
    for index, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        for field_name, kind in fields.items():
            value = row.get(field_name)
            if isinstance(value, str) and value.strip():
                speaker = row.get("name") if isinstance(
                    row.get("name"), str) else None
                out.add(kind, value, speaker=speaker,
                        json_path=[index, field_name])


_DB_FIELDS = {
    "Actors.json": {"name": "name", "nickname": "name", "profile": "description"},
    "Classes.json": {"name": "name"},
    "Skills.json": {"name": "name", "description": "description",
                    "message1": "description", "message2": "description"},
    "Items.json": {"name": "name", "description": "description"},
    "Weapons.json": {"name": "name", "description": "description"},
    "Armors.json": {"name": "name", "description": "description"},
    "Enemies.json": {"name": "name"},
    "States.json": {"name": "name", "message1": "description",
                    "message2": "description", "message3": "description",
                    "message4": "description"},
}


def _parse_system(out: _Collector, data: object) -> None:
    if not isinstance(data, dict):
        return
    if isinstance(data.get("gameTitle"), str) and data["gameTitle"].strip():
        out.add("name", data["gameTitle"], json_path=["gameTitle"])
    for key in ("currencyUnit",):
        if isinstance(data.get(key), str) and data[key].strip():
            out.add("system_terms", data[key], json_path=[key])
    terms = data.get("terms")
    if not isinstance(terms, dict):
        return
    for key in ("basic", "commands", "params"):
        values = terms.get(key)
        if isinstance(values, list):
            for index, value in enumerate(values):
                if isinstance(value, str) and value.strip():
                    out.add("system_terms", value,
                            json_path=["terms", key, index])
    messages = terms.get("messages")
    if isinstance(messages, dict):
        for key in sorted(messages):
            value = messages[key]
            if isinstance(value, str) and value.strip():
                out.add("system_terms", value, json_path=["terms", "messages", key])


def _parse_map_infos(out: _Collector, data: object) -> None:
    if not isinstance(data, list):
        return
    for index, row in enumerate(data):
        if isinstance(row, dict) and isinstance(row.get("name"), str) \
                and row["name"].strip():
            out.add("name", row["name"], json_path=[index, "name"])


def _parse_common_events(out: _Collector, data: object) -> None:
    if not isinstance(data, list):
        return
    for index, event in enumerate(data):
        if not isinstance(event, dict):
            continue
        name = event.get("name") if isinstance(event.get("name"), str) else None
        if name:
            out.add("name", name, json_path=[index, "name"])
        _walk_commands(out, event.get("list"), [index, "list"], speaker=name)


def parse_game(game_root: Path, data_dir: Path) -> list[RawStatement]:
    """Parse every known JSON file under the data dir (sorted, deterministic)."""
    statements: list[RawStatement] = []
    files = sorted(p for p in data_dir.glob("*.json") if p.is_file())
    for path in files:
        rel = path.relative_to(game_root).as_posix()
        out = _Collector(rel)
        data = _load_json(path)
        name = path.name
        if name == "System.json":
            _parse_system(out, data)
        elif name == "MapInfos.json":
            _parse_map_infos(out, data)
        elif name == "CommonEvents.json":
            _parse_common_events(out, data)
        elif name.startswith("Map") and name[3:-5].isdigit():
            _parse_map(out, data)
        elif name in _DB_FIELDS:
            _parse_table(out, data, _DB_FIELDS[name])
        # Unknown files (Tilesets, Animations, plugins...): skipped by design.
        statements.extend(out.statements)
    return statements
