# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""포트 자동 탐색 + 응답 형식 방어.

두 가지 회귀를 막는다:
1) 데스크톱(8765)/개발(8003) 중 어느 쪽이 떠 있든 KEYLENS_BASE_URL 없이 붙어야 한다.
2) 그 포트에 KeyLens가 아닌 다른 프로그램이 떠 있어도 원시 JSONDecodeError/KeyError가
   밖으로 새면 안 된다 - 전부 KeylensEnvError 계열로 정규화돼야 한다.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from keylens_env import client
from keylens_env.exceptions import (
    KeylensEnvError,
    KeylensNotRunningError,
    KeylensServerError,
)

KEYLENS_HEALTH = {"status": "ok", "services": 9, "credentials": 22}


def _serve(routes: dict[str, tuple[int, bytes]]):
    """routes: {경로: (상태코드, 본문바이트)} 로 응답하는 일회용 로컬 서버."""

    class H(BaseHTTPRequestHandler):
        def _reply(self):
            status, body = routes.get(self.path, (404, b"{}"))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = _reply

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch):
    monkeypatch.delenv("KEYLENS_BASE_URL", raising=False)
    monkeypatch.setattr(client, "_resolved_base_url", None)
    yield
    monkeypatch.setattr(client, "_resolved_base_url", None)


def test_picks_second_candidate_when_first_is_dead(monkeypatch):
    """exe 포트가 죽어 있으면 dev 포트로 자동 폴백한다 - 환경변수 설정이 필요 없다."""
    srv, url = _serve({"/health": (200, json.dumps(KEYLENS_HEALTH).encode())})
    try:
        dead = "http://127.0.0.1:1"  # 아무도 안 듣는 포트
        monkeypatch.setattr(client, "CANDIDATE_BASE_URLS", (dead, url))
        assert client.resolve_base_url(force=True) == url
    finally:
        srv.shutdown()


def test_skips_impostor_service_on_the_port(monkeypatch):
    """그 포트에 다른 앱이 떠 있으면 건너뛰고 진짜 KeyLens를 고른다."""
    impostor, imp_url = _serve({"/health": (200, b"<html>other app</html>")})
    real, real_url = _serve({"/health": (200, json.dumps(KEYLENS_HEALTH).encode())})
    try:
        monkeypatch.setattr(client, "CANDIDATE_BASE_URLS", (imp_url, real_url))
        assert client.resolve_base_url(force=True) == real_url
    finally:
        impostor.shutdown()
        real.shutdown()


def test_raises_not_running_when_no_candidate_answers(monkeypatch):
    monkeypatch.setattr(client, "CANDIDATE_BASE_URLS", ("http://127.0.0.1:1",))
    with pytest.raises(KeylensNotRunningError) as exc:
        client.resolve_base_url(force=True)
    assert "KEYLENS_BASE_URL" in str(exc.value)  # 다음 수단을 알려준다


def test_env_var_wins_and_skips_discovery(monkeypatch):
    """사용자가 명시한 주소를 말없이 다른 포트로 바꿔치기하면 안 된다."""
    monkeypatch.setenv("KEYLENS_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setattr(client, "CANDIDATE_BASE_URLS", ("http://127.0.0.1:1",))
    assert client.resolve_base_url(force=True) == "http://127.0.0.1:9999"


def test_non_json_response_becomes_typed_error():
    """예전엔 원시 JSONDecodeError가 그대로 샜다."""
    srv, url = _serve({"/sdk/env": (200, b"<html>not keylens</html>")})
    try:
        with pytest.raises(KeylensServerError) as exc:
            client.fetch_env("c", "/p", base_url=url)
        assert isinstance(exc.value, KeylensEnvError)
    finally:
        srv.shutdown()


def test_missing_values_key_becomes_typed_error():
    """예전엔 원시 KeyError('values')가 그대로 샜다."""
    srv, url = _serve({"/sdk/env": (200, json.dumps({"ok": True}).encode())})
    try:
        with pytest.raises(KeylensServerError):
            client.fetch_env("c", "/p", base_url=url)
    finally:
        srv.shutdown()


def test_fetch_collections_parses_list():
    rows = [{"project": "블로그", "key_count": 3}, {"project": "2026-08-29", "key_count": 1}]
    srv, url = _serve({"/sdk/projects": (200, json.dumps(rows).encode())})
    try:
        assert client.fetch_collections(base_url=url) == rows
    finally:
        srv.shutdown()


def test_fetch_collections_rejects_wrong_shape():
    srv, url = _serve({"/sdk/projects": (200, json.dumps({"nope": 1}).encode())})
    try:
        with pytest.raises(KeylensServerError):
            client.fetch_collections(base_url=url)
    finally:
        srv.shutdown()
