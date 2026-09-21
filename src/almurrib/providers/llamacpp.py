"""llama.cpp server lifecycle helper (stdlib only, no downloads).

Local-first translation reuses the generic OpenAI-compatible transport
against a user-run ``llama-server``. This module only finds, starts and
health-checks that server — binaries and .gguf weights are the user's
(they are hundreds of MB and never bundled).

Typical flow::

    from almurrib.providers.llamacpp import wait_ready
    base_url = wait_ready("http://localhost:8080/v1")  # already running, or
    # start your own: llama-server -m model.gguf --port 8080
    # then configure provider=openai_compat (or llamacpp), model=<served id>
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class LlamaServer:
    """A managed llama-server subprocess (context-managed lifetime)."""

    process: subprocess.Popen
    base_url: str

    def __enter__(self) -> "LlamaServer":
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def stop(self) -> None:
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass

    @property
    def running(self) -> bool:
        return self.process.poll() is None


def health_ok(base_url: str, *, timeout_seconds: float = 5.0) -> bool:
    """True when ``GET {base}/models`` answers (any shape)."""
    request = urllib.request.Request(
        base_url.rstrip("/") + "/models", method="GET")
    try:
        with urllib.request.urlopen(request,
                                    timeout=timeout_seconds) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def wait_ready(base_url: str, *, timeout_seconds: float = 60.0,
               poll_interval: float = 1.0) -> str:
    """Block until a (possibly just-started) server answers.

    Raises TimeoutError with setup guidance instead of hanging forever.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if health_ok(base_url, timeout_seconds=2.0):
            return base_url.rstrip("/")
        time.sleep(poll_interval)
    raise TimeoutError(
        f"no llama.cpp server answered at {base_url} within "
        f"{timeout_seconds:.0f}s",
    )


def start_server(binary: str, model_path: str, *, port: int = 8080,
                 host: str = "127.0.0.1",
                 extra_args: list[str] | None = None,
                 wait_seconds: float = 120.0) -> LlamaServer:
    """Launch ``llama-server -m <model> --port <port>`` and wait for health.

    The caller owns the returned server (use as a context manager).
    """
    from pathlib import Path

    if not Path(binary).is_file():
        raise FileNotFoundError(f"llama.cpp server binary not found: {binary}")
    if not Path(model_path).is_file():
        raise FileNotFoundError(f"model weights not found: {model_path}")
    command = [binary, "-m", model_path, "--host", host, "--port", str(port)]
    command.extend(extra_args or [])
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"cannot start llama-server: {exc}") from exc
    server = LlamaServer(process=process, base_url=f"http://{host}:{port}/v1")
    try:
        wait_ready(server.base_url, timeout_seconds=wait_seconds)
    except Exception:
        server.stop()
        raise
    return server
