# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""CORS 프리플라이트 회귀 테스트.

dev 모드는 프론트(5173)와 백엔드(8003)가 서로 다른 오리진이라, 브라우저가 DELETE·PATCH를
보내기 전에 OPTIONS 프리플라이트를 먼저 던진다. 여기서 거부되면 항목 삭제(DELETE)·
메모/만료일 수정(PATCH)·SDK 디렉토리 해제(DELETE)가 전부 "연결할 수 없어요"로 실패한다.
데스크톱 exe 는 same-origin 이라 이 경로를 타지 않아 증상이 드러나지 않는다 — 그래서 테스트로 고정한다.

프로젝트 관례상 TestClient(httpx→certifi/MPL-2.0)를 쓰지 않으므로, uvicorn 을 임시 포트에
띄우고 표준 라이브러리 urllib 로 실제 프리플라이트를 보낸다.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

HOST = "127.0.0.1"
ORIGIN = "http://localhost:5173"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    import os

    import uvicorn

    os.environ["KEYLENS_VAULT_PATH"] = str(tmp_path_factory.mktemp("cors") / "vault.db")
    sys.modules.pop("app.main", None)
    from app.main import app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base = f"http://{HOST}:{port}"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=1) as r:
                if r.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    else:
        pytest.fail("테스트용 백엔드가 제때 기동하지 못했습니다")

    yield base

    server.should_exit = True
    thread.join(timeout=5)


def _preflight(base: str, path: str, method: str):
    req = urllib.request.Request(
        f"{base}{path}",
        method="OPTIONS",
        headers={"Origin": ORIGIN, "Access-Control-Request-Method": method},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.headers.get("access-control-allow-methods", "")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("access-control-allow-methods", "")


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_preflight_allows_methods_the_frontend_uses(live_server, method):
    status, allowed = _preflight(live_server, "/vault/entries/1", method)
    assert status == 200, f"{method} 프리플라이트가 거부됨({status}) — 브라우저에서 호출 불가"
    assert method in allowed, f"{method} 가 access-control-allow-methods 에 없음: {allowed!r}"


def test_preflight_for_sdk_directory_removal(live_server):
    """RUNTIME-1 '프로젝트 접근' 화면의 디렉토리 해제(DELETE) 경로."""
    status, allowed = _preflight(live_server, "/sdk/projects/blog/directories/1", "DELETE")
    assert status == 200
    assert "DELETE" in allowed
