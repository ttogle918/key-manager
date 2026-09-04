# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""릴리스 zip 을 사용자처럼 받아서 열어보는 검수 테스트 (수동 릴리스 게이트).

왜 필요한가: v0.5.0 의 두 버그(zip 에 금고 동봉, 금고 생성 전 SDK 500)는 백엔드 테스트
338개와 CI 6종을 **전부 통과한 상태에서** 나왔다. 둘 다 "배포물을 압축 해제해 실행한다"는
행동으로만 드러난다. 소스 트리에서 도는 테스트로는 원리적으로 잡을 수 없어서, 그 행동을
그대로 코드로 박아 둔다.

CI 에서는 돌지 않는다(리눅스 러너에 Windows exe 가 없다). `package.py` 로 zip 을 만든 뒤
릴리스를 게시하기 **전에** 로컬에서 돌리는 게이트다:

    cd desktop && python package.py --build
    cd desktop && python -m pytest test_release_artifact.py -v

zip 이 없으면 전부 건너뛴다 - 레포를 막 받은 사람이나 CI 가 실패하지 않도록.

주의: 실행 파일이 GUI 앱이라 검수 중 창이 잠깐 떴다 사라진다. 금고는 압축을 푼 임시
디렉토리 안에만 생기므로 실제 사용 중인 금고는 건드리지 않는다.
"""
from __future__ import annotations

import json
import mimetypes
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

import pytest

import package

HOST = "127.0.0.1"
PORT = 8765  # desktop/app.py 의 고정 포트
BASE = f"http://{HOST}:{PORT}"
BOOT_TIMEOUT_S = 120  # 프리즈된 앱은 첫 임포트가 느리다(onnxruntime 등)
REPO = Path(__file__).resolve().parent.parent
DEMO_SCREENSHOT = REPO / "docs" / "demo" / "openai.png"

# 기본은 이번 버전의 zip. KEYLENS_RELEASE_ZIP 으로 다른 아티팩트를 지정할 수 있다 -
# 게시된 릴리스를 내려받아 검수하거나, 예전 버전에 대고 돌려 "이 테스트가 실제로 실패할 수
# 있는지" 확인할 때 쓴다(회귀 테스트는 실패할 줄 알아야 테스트다).
_ENV_ZIP = os.environ.get("KEYLENS_RELEASE_ZIP")
ZIP_PATH = (
    Path(_ENV_ZIP).expanduser().resolve()
    if _ENV_ZIP
    else package.BUILD / f"KeyLens-v{package._read_version()}-win64.zip"
)

pytestmark = pytest.mark.skipif(
    not ZIP_PATH.exists(),
    reason=f"릴리스 zip 없음 ({ZIP_PATH.name}) - 먼저 `python package.py --build` 실행",
)


def _get(path: str, timeout: float = 30):
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return r.status, r.read()


def _post_image(path: str, image: Path, field: str = "image", timeout: float = 300):
    """멀티파트 업로드를 표준 라이브러리로만 만든다.

    requests/httpx 를 쓰지 않는 이유: 둘 다 certifi(MPL-2.0)를 끌어오는데, 이 프로젝트는
    그것 때문에 httpx 를 일부러 뺐다(backend/requirements-dev.txt 주석). 검수 테스트가
    라이선스 규칙에 구멍을 내면 안 된다.
    """
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{image.name}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode()
    body = head + image.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def _port_is_free() -> bool:
    with socket.socket() as s:
        return s.connect_ex((HOST, PORT)) != 0


@pytest.fixture(scope="module")
def artifact(tmp_path_factory):
    """zip 을 새 디렉토리에 풀어 놓기만 한다(실행 없음)."""
    dest = tmp_path_factory.mktemp("release")
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extractall(dest)
    return dest


@pytest.fixture(scope="module")
def running_app(artifact):
    """압축을 푼 그 자리에서 앱을 띄운다. 사용자가 하는 것과 같은 순서다."""
    if not _port_is_free():
        pytest.fail(
            f"{PORT} 포트를 이미 누가 쓰고 있습니다. 그대로 두면 **다른 프로세스에 물어보고**\n"
            "  배포물이 멀쩡하다고 착각하게 됩니다(실제로 겪은 오진입니다).\n"
            "  실행 중인 KeyLens/개발 서버를 먼저 종료하세요."
        )

    exe = artifact / "KeyLens.exe"
    assert exe.exists(), "zip 안에 KeyLens.exe 가 없습니다"
    proc = subprocess.Popen([str(exe)], cwd=str(artifact))
    # Popen 직후부터 정리 범위에 넣는다. 기동 대기나 소유권 검사에서 실패하면 yield 에
    # 닿지 못해 앱이 살아남고, 다음 실행은 "포트를 누가 쓰고 있다"로 죽는다(실제로 겪었다).
    try:
        deadline = time.time() + BOOT_TIMEOUT_S
        while time.time() < deadline:
            if proc.poll() is not None:
                pytest.fail(f"앱이 기동 중 종료됐습니다 (exit={proc.returncode})")
            try:
                _get("/health", timeout=2)
                break
            except (urllib.error.URLError, OSError, TimeoutError):
                time.sleep(1)
        else:
            pytest.fail(f"{BOOT_TIMEOUT_S}초 안에 응답하지 않았습니다")

        # 응답한 게 정말 **우리가 띄운 그 프로세스**인지 확인한다. 포트 선점 검사만으로는
        # 경합을 다 막지 못하고, 엉뚱한 서버를 검수하면 통과가 아무 의미가 없다.
        #
        # 프리즈된 앱은 금고를 실행 파일 옆에 만드므로, 압축을 푼 디렉토리에 vault.db 가
        # 나타나는 것이 소유권 증거가 된다. 다만 금고 파일은 기동 시점이 아니라 **DB 를 처음
        # 건드릴 때** 생기고 /health 는 DB 를 보지 않으므로, 먼저 /vault/status 를 부른다.
        _get("/vault/status")
        assert (artifact / "vault.db").exists(), (
            "응답한 서버가 압축을 푼 그 앱이 아닙니다 - 다른 프로세스가 포트를 쥐고 있습니다"
        )

        yield artifact
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


# --- 내용물 검사 (앱 실행 없이) ------------------------------------------------

def test_artifact_carries_no_vault_or_secrets():
    """가장 중요한 검사 - 금고가 배포물에 실리면 안 된다.

    package.py 가 압축 전에 걸러내지만, 여기서 다시 본다. 압축 경로가 하나뿐이라는 보장이
    없고(누군가 직접 Compress-Archive 할 수 있다), 실패 비용이 유출이라 이중으로 막는다.
    """
    with zipfile.ZipFile(ZIP_PATH) as zf:
        names = [Path(n).name for n in zf.namelist()]

    assert "vault.db" not in names
    assert not [n for n in names if n.startswith("vault.db")], "SQLite 저널도 안 된다"
    assert not [n for n in names if n.endswith((".sqlite", ".sqlite3"))]
    assert ".env" not in names


def test_artifact_bundles_everything_the_app_needs(artifact):
    """동봉물 누락은 실행해 봐야만 드러난다 - 빌드는 조용히 성공한다."""
    assert (artifact / "frontend" / "dist" / "index.html").exists(), "SPA 누락"
    assert list((artifact / "backend" / "knowledge").glob("*.yaml")), "지식베이스 누락"
    assert list((artifact / "app" / "ocr_models").glob("*.onnx")), "OCR 모델 누락"


# --- 실행 검사 ----------------------------------------------------------------

def test_health_reports_the_full_knowledge_base(running_app):
    status, body = _get("/health")
    data = json.loads(body)

    assert status == 200
    assert data["status"] == "ok"
    # 동봉된 YAML 수와 앱이 실제로 읽어들인 수가 같아야 한다. 파일만 있고 로드에 실패해도
    # 앱은 뜨기 때문에, 파일 존재 확인(위)만으로는 부족하다.
    yaml_count = len(list((running_app / "backend" / "knowledge").glob("*.yaml")))
    assert data["services"] == yaml_count


def test_spa_is_served_with_its_assets(running_app):
    status, body = _get("/")
    assert status == 200

    html = body.decode("utf-8")
    srcs = [s.split('"')[1] for s in html.split('src="')[1:]]
    assert srcs, "index.html 에 스크립트 참조가 없습니다"
    for src in srcs:
        if src.startswith("/"):
            asset_status, asset_body = _get(src)
            assert asset_status == 200, f"자산 404: {src}"
            assert asset_body, f"빈 자산: {src}"


def test_fresh_install_offers_setup_not_unlock(running_app):
    """새로 받은 사용자에게는 금고 만들기가 떠야 한다.

    v0.5.0 처럼 zip 에 vault.db 가 들어가면 여기서 initialized 가 true 로 나올 수 있고,
    그러면 새 사용자가 있지도 않은 비밀번호를 요구받는다.
    """
    _, body = _get("/vault/status")
    assert json.loads(body) == {"initialized": False, "unlocked": False}


def test_sdk_reads_work_before_a_vault_exists(running_app):
    """회귀 방지: 예전에는 여기서 no such table 로 500 이 났다."""
    for path in ("/sdk/pending", "/sdk/projects"):
        status, body = _get(path)
        assert status == 200, path
        assert json.loads(body) == [], path


def test_ocr_and_classification_work_inside_the_frozen_app(running_app):
    """패키징에서 가장 깨지기 쉬운 부분 - RapidOCR/onnxruntime 의 C 확장과 동적 임포트.

    cx_Freeze 가 이걸 놓쳐도 앱은 멀쩡히 뜨고 /health 도 200 을 준다. 실제로 이미지를
    한 장 넣어보는 것 말고는 확인할 방법이 없다.
    """
    if not DEMO_SCREENSHOT.exists():
        pytest.skip(f"데모 스크린샷 없음: {DEMO_SCREENSHOT}")

    status, body = _post_image("/analyze/image", DEMO_SCREENSHOT)
    assert status == 200

    items = json.loads(body)["items"]
    assert items, "OCR 이 아무것도 찾지 못했습니다"
    # backend/tests/test_ocr_demo_screenshots.py 와 같은 기대치(부분집합)를 쓴다.
    assert "OPENAI_API_KEY" in {i["official_env_name"] for i in items}
