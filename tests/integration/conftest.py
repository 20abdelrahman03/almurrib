"""Integration-test fixtures.

These tests exercise the CLI/workflow, which reads configuration from the
environment and a local ``.env``. To stay deterministic and offline, every
integration test runs isolated from any real ``.env`` or ``ALMURRIB_*`` /
provider env vars that happen to exist on the developer machine.
"""

import pytest

from almurrib.core.config import ENV_PREFIX


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    """Neutralize ambient provider configuration for the test duration."""
    for key in list(__import__("os").environ):
        if key.startswith(ENV_PREFIX):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)  # no .env in the temp working dir
    yield
