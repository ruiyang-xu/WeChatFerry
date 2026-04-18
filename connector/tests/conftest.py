from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _StubHandler(BaseHTTPRequestHandler):
    canned: dict = {}

    def log_message(self, *args, **kwargs):  # silence
        pass

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        if self.path == "/api/chat":
            body = {"message": {"content": json.dumps(self.canned)}}
        else:
            body = {}
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture
def ollama_stub():
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), _StubHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)
    try:
        yield {"endpoint": f"http://127.0.0.1:{port}", "handler": _StubHandler}
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "connector.db")
