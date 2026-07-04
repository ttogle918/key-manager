# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Ollama 서비스 분류 테스트 (값 기반). 모든 값은 더미."""
import pytest

from app.classify.pipeline import analyze
from app.knowledge import load_knowledge_base
from app.models import AnalyzeRequest

# 더미 Ollama 키 포맷: 32 hex + '.' + 24 base62 (명백한 가짜 — 실제 키 아님)
PASTE = "abcdef0123456789abcdef0123456789.DummyOllamaSuffix1234567"
# OCR 이 1→i 로 오독해도 문자클래스(영숫자)를 벗어나지 않아 여전히 매치된다.
OCR = "abcdef0123456789abcdef0123456789.DummyOllamaSuffixi234567"


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


def test_pasted_key_classifies(kb):
    resp = analyze(AnalyzeRequest(text=f"OLLAMA_API_KEY={PASTE}"), kb)
    envs = {it.official_env_name: it for it in resp.items}
    assert "OLLAMA_API_KEY" in envs
    assert envs["OLLAMA_API_KEY"].confidence == "high"
    assert envs["OLLAMA_API_KEY"].service == "ollama"


def test_ocr_value_still_classifies(kb):
    """OCR 오독(1→i) 값도 포맷 문자클래스 안이라 분류된다 — 값은 복붙 전제라 충분."""
    resp = analyze(AnalyzeRequest(text=OCR), kb)
    assert any(it.official_env_name == "OLLAMA_API_KEY" for it in resp.items)


def test_bare_32hex_not_mistaken_for_ollama(kb):
    """카카오류 32hex 단독은 '.suffix' 가 없어 ollama 로 오식별되지 않는다."""
    resp = analyze(AnalyzeRequest(text="a2b3c4d5e6e7a8b9c2d3e4e5a6b7c8d9"), kb)
    assert all(it.official_env_name != "OLLAMA_API_KEY" for it in resp.items)


def test_random_text_not_matched(kb):
    resp = analyze(AnalyzeRequest(text="just some words, not a key at all"), kb)
    assert all(it.official_env_name != "OLLAMA_API_KEY" for it in resp.items)
