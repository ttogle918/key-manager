# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env ↔ 실제 KeyLens 백엔드 end-to-end 검증(2개).

이 파일만 backend/ 의존성(fastapi, uvicorn 등)이 필요하다 — keylens_env 패키지 자체의
런타임 의존성이 아니라 이 레포 안에서 도는 테스트 전용 요구사항이다. keylens-env는
backend/ 코드를 import하지 않는다는 Global Constraint는 이 파일에는 적용되지 않는다
(테스트 전용 예외 — 계획의 Global Constraints 참고).

단독으로 실행한다(backend/tests/ 스위트와 같은 pytest 프로세스에서 함께 돌리지 않는다) —
app.main이 모듈 임포트 시점에 KEYLENS_VAULT_PATH를 읽어 VAULT 싱글턴을 구성하므로,
다른 테스트가 이미 app.main을 다른 경로로 임포트해 뒀으면 캐시된 모듈이 재사용되어
이 파일의 격리가 깨진다.
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import keylens_env  # noqa: E402
from keylens_env.exceptions import KeylensLockedError  # noqa: E402

MASTER = "correct horse battery staple"
HOST = "127.0.0.1"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _wait_ready(url: str, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.1)
    return False


def _post(base_url: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{base_url}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


@pytest.fixture
def live_backend(tmp_path, monkeypatch):
    """실제 app.main:app을 uvicorn으로 임시 포트에 기동(desktop/app.py의 _wait_ready 패턴과 동일)."""
    import uvicorn

    monkeypatch.setenv("KEYLENS_VAULT_PATH", str(tmp_path / "vault.db"))
    sys.modules.pop("app.main", None)  # 매 테스트마다 새 vault.db로 재구성되도록 재임포트
    from app.main import app

    port = _free_port()
    config = uvicorn.Config(app, host=HOST, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    assert _wait_ready(f"http://{HOST}:{port}/health"), "테스트용 백엔드가 제때 기동하지 못했습니다"

    yield f"http://{HOST}:{port}"

    server.should_exit = True
    thread.join(timeout=5)


def test_load_env_end_to_end_against_real_backend(live_backend, monkeypatch, tmp_path):
    monkeypatch.setenv("KEYLENS_BASE_URL", live_backend)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    _post(live_backend, "/vault/init", {"password": MASTER})
    _post(
        live_backend,
        "/vault/entries",
        {
            "service": "openai", "kind": "api_key", "official_name": "OPENAI_API_KEY",
            "value": "sk-dummy", "project": "블로그",
        },
    )
    _post(live_backend, f"/sdk/projects/{quote('블로그')}/directories", {"path": str(tmp_path)})

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")

    keylens_env.load_env()

    import os

    assert os.environ["OPENAI_API_KEY"] == "sk-dummy"


def test_load_env_raises_locked_when_vault_uninitialized(live_backend, monkeypatch, tmp_path):
    # 금고를 초기화하지 않은 상태 — sdk_env()는 초기화 여부와 무관하게 "잠김"과 동일하게 다룬다.
    monkeypatch.setenv("KEYLENS_BASE_URL", live_backend)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".keylens.toml").write_text('project = "블로그"\n', encoding="utf-8")

    with pytest.raises(KeylensLockedError):
        keylens_env.load_env()
