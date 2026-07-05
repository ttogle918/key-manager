# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 데스크톱 런처 (A) — 로컬 웹앱을 네이티브 창 하나로 감싼다.

동작:
  1. FastAPI 백엔드(app.main:app)에 빌드된 프론트(frontend/dist)를 정적 서빙으로 마운트
     → API와 SPA가 **같은 오리진**에서 제공된다(포트 상관없이 same-origin, CORS 불필요).
  2. uvicorn 을 백그라운드 스레드로 127.0.0.1 로컬에만 바인딩해 기동.
  3. pywebview 로 OS 내장 웹뷰 창을 띄워 그 로컬 주소를 로드.
  4. 창을 닫으면 프로세스가 종료되며 서버(데몬 스레드)도 함께 내려간다.

전부 로컬이다 — 외부 서버 없음, 데이터는 이 기기의 backend/vault.db(암호문)에만.
서버 조립(create_app/serve)과 창(main)은 분리해, GUI 없이도 서빙을 검증할 수 있게 했다.
"""
from __future__ import annotations

import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import uvicorn
from starlette.staticfiles import StaticFiles

HOST = "127.0.0.1"
# 데스크톱 전용 포트(dev 8003 과 분리해 동시 실행 충돌 회피). 고정이지만 same-origin이라 무관.
PORT = 8765
_ROOT = Path(__file__).resolve().parent.parent
DIST = _ROOT / "frontend" / "dist"

# 어느 위치에서 실행하든 backend/ 의 `app` 패키지를 찾도록 경로를 잡는다(더블클릭 실행 대비).
sys.path.insert(0, str(_ROOT / "backend"))

from app.main import app  # noqa: E402 — sys.path 설정 후 임포트


def mount_spa() -> None:
    """빌드된 SPA(frontend/dist)를 '/' 에 정적 마운트.

    API 라우트(/analyze·/vault·/knowledge·/health)는 app.main 에서 이미 등록되어
    라우팅 순서상 먼저 매칭되고, 나머지 경로만 이 정적 마운트(SPA)로 떨어진다.
    """
    if not DIST.is_dir():
        raise SystemExit(
            "frontend/dist 가 없습니다 — 먼저 프론트를 빌드하세요:\n"
            "  cd frontend && npm ci && npm run build"
        )
    if any(getattr(r, "name", None) == "spa" for r in app.router.routes):
        return  # 중복 마운트 방지(재호출 안전)
    app.mount("/", StaticFiles(directory=str(DIST), html=True), name="spa")


def serve() -> None:
    """uvicorn 을 로컬에만 바인딩해 실행(블로킹)."""
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def _wait_ready(timeout: float = 20.0) -> bool:
    """서버가 /health 에 응답할 때까지 대기(스레드 기동 레이스 방지)."""
    deadline = time.monotonic() + timeout
    url = f"http://{HOST}:{PORT}/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.15)
    return False


def main() -> None:
    import webview  # 지연 임포트 — 서버 검증(mount/serve)은 pywebview 없이도 돈다.

    mount_spa()
    threading.Thread(target=serve, daemon=True).start()
    if not _wait_ready():
        raise SystemExit("백엔드가 제때 기동하지 못했습니다.")
    # localhost 로 로드 → 페이지 오리진과 상대경로 API 요청이 같은 오리진(same-origin).
    webview.create_window(
        "KeyLens", f"http://localhost:{PORT}", width=1120, height=780, min_size=(900, 620)
    )
    webview.start()


if __name__ == "__main__":
    main()
