"""Root conftest: make ``src/`` importable without requiring installation.

Running ``pytest`` from the repository root works out of the box; for the
installed experience use ``pip install -e .[dev]``.
"""

import sys
from pathlib import Path

SRC = str(Path(__file__).parent / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
