# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""엣지케이스 안정화 (OSS-1) — 잘못된 입력에도 크래시 없음. 모든 값 더미."""
import pytest

from app.classify.pipeline import analyze
from app.knowledge import load_knowledge_base
from app.models import AnalyzeRequest


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


@pytest.mark.parametrize(
    "req",
    [
        AnalyzeRequest(),  # 빈 요청
        AnalyzeRequest(text=""),  # 빈 문자열
        AnalyzeRequest(text="   \n\t  "),  # 공백만
        AnalyzeRequest(url="not a url at all"),  # 깨진 URL
        AnalyzeRequest(text="\x00\x01\x02 제어문자 섞임"),  # 제어문자
        AnalyzeRequest(text="=" * 5000),  # 구분자 폭탄
        AnalyzeRequest(text="키=" * 3000),  # 반복 대입 패턴
        AnalyzeRequest(text="a" * 50_000),  # 큰 단일 토큰
    ],
)
def test_analyze_never_crashes(kb, req):
    """어떤 잘못된 입력에도 예외 없이 결과(빈 목록 가능)를 돌려준다."""
    resp = analyze(req, kb)
    assert resp.count == len(resp.items)  # 계약 일관성


def test_analyze_ignores_garbage_but_finds_real_key(kb):
    """잡음 속에서도 명확한 키는 찾는다(오식별 없이)."""
    text = "!!! 주석 #무시 \x00 OPENAI_API_KEY=sk-proj-" + "a" * 20 + " ??? 끝"
    envs = {it.official_env_name for it in analyze(AnalyzeRequest(text=text), kb).items}
    assert "OPENAI_API_KEY" in envs


def test_input_length_caps_are_declared():
    """API 입력 상한이 모델에 선언돼 있어 폭주 입력을 막는다."""
    from app.models import AnalyzeRequest as AR

    fields = AR.model_fields
    assert fields["text"].metadata  # max_length 제약 존재
    assert fields["url"].metadata
