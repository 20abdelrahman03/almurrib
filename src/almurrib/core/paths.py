"""Application base directory resolution.

The packaged EXE must not depend on the user's launch working directory:
when frozen, configuration and default data paths live next to the
executable; during development they live in the current working directory.
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_base_dir() -> Path:
    """Directory that owns .env / default database / default output."""
    if getattr(sys, "frozen", False):
        # PyInstaller onefile/one-dir: the real EXE location.
        return Path(sys.executable).resolve().parent
    return Path.cwd()
