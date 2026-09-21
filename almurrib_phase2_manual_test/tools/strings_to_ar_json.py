"""TEST HARNESS ONLY - not a production engine adapter.

Converts Almurrib's exported strings.rpy (old/new pairs) back into the
browser game's dialogue_ar.json, keyed by dialogue id via exact source
match. Warns loudly on missing or ambiguous mappings instead of guessing.

Usage:
    python tools/strings_to_ar_json.py <strings.rpy> [-o output/dialogue_ar.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if not args:
        print("usage: strings_to_ar_json.py <strings.rpy> [-o out.json]",
              file=sys.stderr)
        return 2
    src = Path(args[0])
    out = Path(args[2]) if len(args) > 2 and args[1] == "-o" else \
        ROOT / "output" / "dialogue_ar.json"

    sys.path.insert(0, str(Path("src").resolve()))
    sys.path.insert(0, str(ROOT.parent / "src"))  # Almurrib repo checkout
    from almurrib.engine_adapters.renpy.parser import parse_rpy

    pairs = parse_rpy(src.resolve(), game_root=src.resolve().parent)
    by_source: dict[str, str] = {}
    for statement in pairs:
        if statement.translation:
            by_source.setdefault(statement.text, statement.translation)

    dialogue = json.loads(
        (ROOT / "game_data" / "dialogue.json").read_text(encoding="utf-8"))
    ar: dict[str, dict] = {}
    missing: list[str] = []
    for node in dialogue["nodes"]:
        lines: dict[str, str] = {}
        if node["text"] in by_source:
            lines["text"] = by_source[node["text"]]
        else:
            missing.append(f"{node['id']}:text")
        for choice in node.get("choices", []):
            if choice["text"] in by_source:
                lines[f"choice:{choice['text']}"] = by_source[choice["text"]]
            else:
                missing.append(f"{node['id']}:choice")
        ar[node["id"]] = {"speaker": node.get("speaker"), "lines": lines}

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"generated_from": str(src), "dialogue": ar},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out} ({len(ar)} nodes)")
    if missing:
        print(f"WARNING: {len(missing)} strings without translation:")
        for item in missing[:10]:
            print(f"  - {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
