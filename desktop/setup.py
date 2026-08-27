# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""cx_Freeze 패키징 — KeyLens 데스크톱 앱을 단일 실행 파일(.exe/.app)로 묶는다.

패키저로 cx_Freeze 를 쓰는 이유: **PSF 계열 permissive 라이선스**라 이 프로젝트의
permissive-only 규칙에 부합한다(카피레프트 없음). PyInstaller(GPL+예외)의 대안.

사전 준비:
  1) 프론트 빌드:  cd frontend && npm ci && npm run build      (frontend/dist 생성)
  2) 의존성 설치:  pip install -r desktop/requirements.txt cx_Freeze
빌드:
  cd desktop && python setup.py build
  → build/exe.<플랫폼>/KeyLens(.exe) 실행 파일 + 옆에 frontend/dist·backend/knowledge 동봉

결과물(build/·dist/)은 용량이 커 저장소에 커밋하지 않고 GitHub Releases 아티팩트로만 배포한다.
"""
import sys
from pathlib import Path

from cx_Freeze import Executable, setup

ROOT = Path(__file__).resolve().parent.parent
# cx_Freeze 모듈 파인더가 backend/ 의 `app` 패키지를 찾도록.
sys.path.insert(0, str(ROOT / "backend"))

# 실행 파일 옆에 동봉할 데이터 — app.py 가 exe 기준 상대경로(frozen)로 찾는다.
include_files = [
    (str(ROOT / "frontend" / "dist"), "frontend/dist"),
    (str(ROOT / "backend" / "knowledge"), "backend/knowledge"),
    # CORE-3(백엔드 RapidOCR 이전) 이후 필요 — 빠뜨리면 exe 안에서 "모델이 벤더링 안 됨" 오류.
    (str(ROOT / "backend" / "app" / "ocr_models"), "app/ocr_models"),
]

build_exe_options = {
    "packages": [
        "app", "uvicorn", "fastapi", "starlette", "pydantic", "pydantic_core",
        "cryptography", "yaml", "webview", "anyio", "click", "h11", "plyer",
        # RapidOCR(CORE-3, 백엔드 이전) — C 확장·동적 임포트가 많아 cx_Freeze 자동 추적이 놓치기 쉬움.
        "rapidocr", "onnxruntime", "cv2", "numpy", "PIL", "shapely", "pyclipper",
    ],
    "include_files": include_files,
    "excludes": ["tkinter", "unittest", "pytest", "test"],
}

# Windows 는 콘솔 창 없는 GUI 실행 파일로 (cx_Freeze 8.x 의 base 이름은 "gui").
base = "gui" if sys.platform == "win32" else None

setup(
    name="KeyLens",
    version="0.3.0",
    description="KeyLens — 로컬 자격증명 분류·암호화 금고 (데스크톱)",
    options={"build_exe": build_exe_options},
    executables=[Executable(str(Path(__file__).parent / "app.py"), base=base, target_name="KeyLens")],
)
