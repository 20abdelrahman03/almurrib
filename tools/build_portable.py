"""Portable release builder (stdlib zip, no installer framework).

Packages dist/Almurrib.exe + a run README into
dist/Almurrib-portable-<version>.zip. No admin rights, no installer,
nothing written outside the unzipped folder (config/DB/output resolve
next to the exe). Velopack/SignPath evaluated and deliberately not
adopted (see docs/TOOLS_AND_LICENSES.md).

Usage:
    .venv\\Scripts\\python tools/build_portable.py [--version X.Y.Z]
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="build the portable zip")
    parser.add_argument("--version", default="0.1.0")
    args = parser.parse_args(argv)

    exe = ROOT / "dist" / "Almurrib.exe"
    if not exe.is_file():
        print("error: build the EXE first (python build_exe.py)", file=sys.stderr)
        return 2
    out = ROOT / "dist" / f"Almurrib-portable-{args.version}.zip"
    readme = (
        "Almurrib (المعرب) portable - no install needed.\n"
        "1. Unzip anywhere and double-click Almurrib.exe.\n"
        "2. Pick a game folder, provider + model + key, press START.\n"
        "3. Config (.env), database and output live next to the exe.\n"
        "Unity/Argos extras are NOT included: use desktop Python with\n"
        '  pip install "almurrib[unity]" / "almurrib[offline]" for those.\n'
    )
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(exe, "Almurrib.exe")
        bundle.writestr("READ_ME.txt", readme)
    print(f"OK: {out} ({out.stat().st_size // 1024 // 1024} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
