"""Deterministic acceptance loop for the Station 7 fixture (no key, no money).

rpy/ -> extract -> deterministic provider -> export strings.rpy ->
output/dialogue_ar.json via strings_to_ar_json.py.
Proves every mechanical step; live providers only change the TEXT.

Usage (from the Almurrib repo root):
    .\\.venv\\Scripts\\python almurrib_phase2_manual_test\\tools\\run_deterministic.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FIX = Path(__file__).resolve().parents[1]
REPO = FIX.parent
sys.path.insert(0, str(REPO / "src"))

from almurrib.core.pipeline import LocalizationPipeline
from almurrib.core.workflow import extract_and_store, translate_entries
from almurrib.engine_adapters import default_adapters
from almurrib.engine_adapters.renpy.reinject import write_translation_patch
from almurrib.providers.fake import FakeProvider
from almurrib.storage.database import Database


def main() -> int:
    game = FIX / "rpy"
    db_path = FIX / "output" / "acceptance.db"
    if db_path.exists():
        db_path.unlink()

    pipeline = LocalizationPipeline(adapters=default_adapters())
    with Database(db_path) as db:
        entries, project_id = extract_and_store(pipeline, game, db)
        print("extracted:", len(entries))
        stats = translate_entries(entries, db, FakeProvider(),
                                  project_id=project_id)
        print("translated:", stats.api_translated, "failed:", stats.failed)
        out = FIX / "output" / "almurrib_out"
        written = write_translation_patch(entries, target_lang="ar",
                                          output_dir=out)
        print("exported:", written)

    rpy = out / "game" / "tl" / "ar" / "strings.rpy"
    rc = subprocess.run([
        sys.executable, str(FIX / "tools" / "strings_to_ar_json.py"),
        str(rpy), "-o", str(FIX / "output" / "dialogue_ar.json"),
    ]).returncode
    print("bridge rc:", rc)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
