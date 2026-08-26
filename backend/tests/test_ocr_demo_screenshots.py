# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""백엔드 OCR(RapidOCR, CORE-3 백엔드 이전) 회귀 — 데모 스크린샷 8종을 직접 읽어 분류한다.

브라우저 tesseract.js 골든 픽스처(test_demo_fixtures.py)와 달리, 이 경로는 이미지→분류를
한 번에 검증한다(RapidOCR는 ONNX 추론이라 결정적 — 스냅샷 텍스트를 따로 커밋할 필요 없음).
한국어 인식 모델이 로컬에 벤더링돼 있지 않으면(scripts/vendor_ocr_models.py 미실행) 건너뛴다.
"""
from pathlib import Path

import pytest

from app.classify.pipeline import analyze
from app.knowledge import load_knowledge_base
from app.models import AnalyzeRequest
from app.ocr import _KOREAN_REC_MODEL, run_ocr

DEMO_DIR = Path(__file__).parent.parent.parent / "docs" / "demo"

pytestmark = pytest.mark.skipif(
    not _KOREAN_REC_MODEL.exists(),
    reason="OCR 모델 미벤더링 — python backend/scripts/vendor_ocr_models.py 먼저 실행",
)

# (파일, 최소 기대 env) — ⊆(부분집합)로 둬 OCR 개선으로 더 잡혀도 회귀로 안 걸린다.
# openai.png의 OPENAI_ORG_ID("org-…")는 RapidOCR 한국어 인식 모델이 "g"를 탈락시켜
# "or-…"로 오독 — 순수 문자 인식 오류(공백 삽입과 달리 재결합으로 못 고침). 알려진 한계로 기록.
CASES = [
    ("notion", {"NOTION_API_KEY", "NOTION_DATABASE_ID"}),
    ("kakao", {"KAKAO_REST_API_KEY", "KAKAO_JS_KEY", "KAKAO_ADMIN_KEY", "KAKAO_NATIVE_APP_KEY"}),
    ("gcp", {"GOOGLE_API_KEY"}),
    ("openai", {"OPENAI_API_KEY"}),
    ("github", {"GITHUB_TOKEN"}),
    ("aws", {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"}),
    ("slack", {"SLACK_BOT_TOKEN", "SLACK_USER_TOKEN"}),
    ("stripe", {"STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY"}),
]


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


@pytest.mark.parametrize("name, expected", CASES)
def test_demo_screenshot_ocr_classifies(kb, name, expected):
    image_bytes = (DEMO_DIR / f"{name}.png").read_bytes()
    text = run_ocr(image_bytes)
    resp = analyze(AnalyzeRequest(text=text), kb)
    got = {it.official_env_name for it in resp.items if it.official_env_name}
    assert expected <= got, f"{name}: 기대 {expected} 중 누락 {expected - got} (got={got})"
