# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""client.py — 표준 라이브러리 http.server로 가짜 KeyLens 서버를 흉내 내 상태코드→예외 매핑을 검증."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from keylens_env import client
from keylens_env.exceptions import (
    KeylensApprovalPendingError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)


class _Handler(BaseHTTPRequestHandler):
    status_code = 200
    body: dict = {"values": {"OPENAI_API_KEY": "sk-dummy"}}

    def do_POST(self):  # noqa: N802 - http.server 관례 메서드명
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(self.status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.body).encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A002 - 테스트 출력 조용히
        pass


@pytest.fixture
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=2)


def _base_url(server: HTTPServer) -> str:
    return f"http://127.0.0.1:{server.server_port}"


def test_fetch_env_success(fake_server):
    _Handler.status_code = 200
    _Handler.body = {"values": {"OPENAI_API_KEY": "sk-dummy"}}
    values = client.fetch_env("블로그", "/repo/blog", base_url=_base_url(fake_server))
    assert values == {"OPENAI_API_KEY": "sk-dummy"}


def test_fetch_env_locked_raises(fake_server):
    _Handler.status_code = 401
    _Handler.body = {"detail": "잠김"}
    with pytest.raises(KeylensLockedError):
        client.fetch_env("블로그", "/repo/blog", base_url=_base_url(fake_server))


def test_fetch_env_approval_pending_raises(fake_server):
    _Handler.status_code = 403
    _Handler.body = {"detail": "승인 대기"}
    with pytest.raises(KeylensApprovalPendingError):
        client.fetch_env("블로그", "/repo/blog", base_url=_base_url(fake_server))


def test_fetch_env_unexpected_status_raises_server_error(fake_server):
    _Handler.status_code = 422
    _Handler.body = {"detail": "복호화 실패"}
    with pytest.raises(KeylensServerError):
        client.fetch_env("블로그", "/repo/blog", base_url=_base_url(fake_server))


def test_fetch_env_connection_refused_raises_not_running():
    with pytest.raises(KeylensNotRunningError):
        client.fetch_env("블로그", "/repo/blog", base_url="http://127.0.0.1:1")
