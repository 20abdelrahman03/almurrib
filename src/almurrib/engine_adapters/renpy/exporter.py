"""Human-readable export of normalized entries (JSON).

Lets developers inspect exactly what extraction produced without opening
the SQLite database. The output is deterministic (sorted keys, stable
entry order) so fixture exports can be diffed in tests.
"""

from __future__ import annotations

import json
from pathlib import Path

from almurrib.core.model import LocalizationEntry


def entries_to_json(entries: list[LocalizationEntry]) -> str:
    payload = {
        "format": "almurrib-extraction",
        "format_version": 1,
        "entry_count": len(entries),
        "entries": [entry.to_dict() for entry in entries],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def export_json(entries: list[LocalizationEntry], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(entries_to_json(entries), encoding="utf-8")
    return out_path
