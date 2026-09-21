"""llama.cpp lifecycle tests (no binary needed; stdlib HTTP fakes only)."""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from almurrib.providers.llamacpp import (
    LlamaServer,
    health_ok,
    start_server,
    wait_ready,
)


class _QuietHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"data": []}')

    def log_message(self, *args):
        pass


@pytest.fixture()
def _server():
    httpd = HTTPServer(("127.0.0.1", 0), _QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()


def test_health_ok_true_and_false(_server):
    assert health_ok(_server) is True
    assert health_ok("http://127.0.0.1:1/v1", timeout_seconds=1.0) is False


def test_wait_ready_returns_normalized(_server):
    assert wait_ready(_server, timeout_seconds=10.0).endswith("/v1")


def test_wait_ready_times_out_with_guidance():
    with pytest.raises(TimeoutError) as exc_info:
        wait_ready("http://127.0.0.1:1/v1", timeout_seconds=1.0,
                   poll_interval=0.2)
    assert "llama.cpp server" in str(exc_info.value)


def test_start_server_validates_paths(tmp_path):
    with pytest.raises(FileNotFoundError):
        start_server(str(tmp_path / "nope.exe"), str(tmp_path / "m.gguf"))
    binary = tmp_path / "llama-server.exe"
    binary.write_bytes(b"x")
    with pytest.raises(FileNotFoundError):
        start_server(str(binary), str(tmp_path / "m.gguf"))


def test_server_context_stops_process():
    import subprocess

    proc = subprocess.Popen(["cmd", "/c", "timeout", "/t", "60", "/nobreak"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    with LlamaServer(process=proc, base_url="http://x/v1") as server:
        assert server.running
    assert not server.running
