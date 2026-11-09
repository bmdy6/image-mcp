from __future__ import annotations

import base64
import io
import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    for key in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "IMAGE_MODEL", "IMAGE_MCP_OUTPUT_DIR", "IMAGE_MCP_ALLOW_FAKE_IP"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("IMAGE_MCP_OUTPUT_DIR", str(tmp_path / "output"))
    connect = socket.socket.connect

    def local_only(sock, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1"):
            raise AssertionError("External network disabled in tests")
        return connect(sock, address)

    monkeypatch.setattr(socket.socket, "connect", local_only)


@pytest.fixture
def png():
    buf = io.BytesIO()
    Image.new("RGB", (24, 12), "blue").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def backend(png):
    requests = []
    state = {"status": 200, "body": {"data": [{"b64_json": base64.b64encode(png).decode()}]}}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append((self.path, dict(self.headers), body))
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            value = state["body"]
            self.wfile.write(value if isinstance(value, bytes) else json.dumps(value).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests, state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
