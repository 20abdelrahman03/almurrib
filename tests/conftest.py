"""Shared test fixtures."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


@pytest.fixture(scope="session")
def renpy_fixture_dir() -> Path:
    """Path to the tiny deterministic Ren'Py fixture."""
    return FIXTURES / "renpy_tiny"
