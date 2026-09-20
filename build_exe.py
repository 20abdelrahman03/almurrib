"""Build the standalone Windows executable with PyInstaller.

Usage:
    .venv\\Scripts\\python.exe build_exe.py

Produces dist\\Almurrib.exe (windowed, single-file). The exe launches the
GUI directly — no Python or CLI knowledge required to run it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def main() -> int:
    pyinstaller = [sys.executable, "-m", "PyInstaller"]
    command = pyinstaller + [
        "--noconfirm",
        "--clean",
        str(ROOT / "almurrib.spec"),
    ]
    print("building:", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    exe = DIST / "Almurrib.exe"
    if exe.exists():
        print(f"OK: {exe}")
        return 0
    print("build finished but Almurrib.exe was not found in dist/", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
