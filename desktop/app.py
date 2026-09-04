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

import os
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

# 소스 실행이면 레포 루트, 패키징된 실행 파일(cx_Freeze/PyInstaller)이면 exe 위치를 기준으로 잡는다.
FROZEN = getattr(sys, "frozen", False)
_BASE = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
DIST = _BASE / "frontend" / "dist"

# ⚠️ app.main 은 임포트 시점에 KB·금고를 env 로 구성하므로, 반드시 그 전에 환경을 잡는다.
os.environ.setdefault("KEYLENS_KNOWLEDGE_DIR", str(_BASE / "backend" / "knowledge"))
if FROZEN:
    # 실행 파일 옆에 금고를 둔다(쓰기 가능 위치). 소스 모드는 backend/vault.db 기본값 유지.
    os.environ.setdefault("KEYLENS_VAULT_PATH", str(_BASE / "vault.db"))
    # 소스 모드에서만 backend/ 를 경로에 추가(패키징 시 app 패키지는 번들에 포함됨).
else:
    sys.path.insert(0, str(_BASE / "backend"))

from app import desktop  # noqa: E402 — 같은 이유
from app.main import app, VAULT  # noqa: E402 — 경로·환경 설정 후 임포트


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


def _build_directory_picker(webview, window):
    """네이티브 폴더 선택창을 여는 함수를 만든다(백엔드가 /desktop/pick-directory 에서 호출).

    브라우저에서는 이걸 흉내낼 수 없다 - 웹 표준이 보안상 절대경로를 주지 않는다. 그래서
    폴더 찾기는 데스크톱 앱에서만 되고, 백엔드는 이 함수가 주입됐는지로 기능 유무를 판단한다.

    pywebview 6.x 의 FOLDER_DIALOG 상수는 폐기 예정이라 FileDialog.FOLDER 를 쓴다.
    반환값은 고른 경로들의 시퀀스이거나, 사용자가 취소하면 None 이다.
    """

    def pick() -> str | None:
        chosen = window.create_file_dialog(webview.FileDialog.FOLDER)
        if not chosen:
            return None
        return str(chosen[0])

    return pick


def main() -> None:
    import webview  # 지연 임포트 — 서버 검증(mount/serve)은 pywebview 없이도 돈다.

    import notify  # 지연 임포트 — 같은 이유(GUI 의존 없이 mount_spa/serve만 쓰는 경로 보호)

    mount_spa()
    threading.Thread(target=serve, daemon=True).start()
    if not _wait_ready():
        raise SystemExit("백엔드가 제때 기동하지 못했습니다.")
    # localhost 로 로드 → 페이지 오리진과 상대경로 API 요청이 같은 오리진(same-origin).
    window = webview.create_window(
        "KeyLens", f"http://localhost:{PORT}", width=1120, height=780, min_size=(900, 620)
    )
    VAULT.set_pending_hook(notify.build_notifier(window))
    desktop.set_directory_picker(_build_directory_picker(webview, window))
    webview.start()


if __name__ == "__main__":
    main()
