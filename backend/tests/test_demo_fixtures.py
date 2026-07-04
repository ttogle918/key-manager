# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""DEMO-1 회귀 — 데모 스크린샷의 OCR 재구성 결과를 분류해 기대 env 를 확인한다.

파이프라인: docs/demo/*.png → (브라우저 tesseract.js OCR + reconstruct) → *.recon.txt(골든) → Stage1/2 분류.
OCR 단계(프론트)는 결정적이지만 파이썬에서 재현할 수 없어, 그 출력(재구성 텍스트)을 골든 픽스처로 커밋한다.
이 테스트는 그 골든 텍스트에 대한 **분류 계약**을 지킨다(빠르고 결정적).
재생성: `python docs/demo/generate.py` → 프론트 OCR 재실행(docs/demo/README.md 참고).

모든 값은 더미(placeholder)다. 기대는 `⊆`(부분집합)으로 둬, OCR 개선으로 더 잡히면 통과가 깨지지 않는다.
"""
from pathlib import Path

import pytest

from app.classify.pipeline import analyze
from app.knowledge import load_knowledge_base
from app.models import AnalyzeRequest

FIXTURES = Path(__file__).parent / "fixtures" / "demo"

# (파일, 최소 기대 env). kakao JS/Native 는 한글 라벨("키"/"앱") OCR 오독으로 현재 미검출 —
# 알려진 한계(CORE-3 전처리 후속에서 개선). 나머지는 값·라벨 OCR 이 안정적으로 분류된다.
CASES = [
    ("notion", {"NOTION_API_KEY", "NOTION_DATABASE_ID"}),
    ("kakao", {"KAKAO_REST_API_KEY", "KAKAO_ADMIN_KEY"}),
    ("gcp", {"GOOGLE_API_KEY"}),
    ("openai", {"OPENAI_API_KEY", "OPENAI_ORG_ID"}),
]


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


@pytest.mark.parametrize("name, expected", CASES)
def test_demo_screenshot_classifies(kb, name, expected):
    text = (FIXTURES / f"{name}.recon.txt").read_text(encoding="utf-8")
    resp = analyze(AnalyzeRequest(text=text), kb)
    got = {it.official_env_name for it in resp.items if it.official_env_name}
    assert expected <= got, f"{name}: 기대 {expected} 중 누락 {expected - got} (got={got})"
