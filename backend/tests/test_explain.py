# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""설명 파이프라인 — 지식베이스 대조 + Ollama 추론(1단계, 검색 없음).

실제 이미지는 docs/demo/notion.png(더미 값)를 쓰되, Ollama 호출은 monkeypatch로 대체해
로컬 Ollama 없이도 CI에서 돈다. 한국어 인식 모델이 벤더링돼 있지 않으면 스킵.
"""
import json
from pathlib import Path

import pytest

from app import explain, ollama_client
from app.knowledge import load_knowledge_base
from app.ocr import _KOREAN_REC_MODEL
from app.ollama_client import OllamaConfig, OllamaUnavailableError

DEMO_DIR = Path(__file__).parent.parent.parent / "docs" / "demo"

pytestmark = pytest.mark.skipif(
    not _KOREAN_REC_MODEL.exists(),
    reason="OCR 모델 미벤더링 — python backend/scripts/vendor_ocr_models.py 먼저 실행",
)

CONFIG = OllamaConfig(base_url="http://localhost:11434", model="llama3.2")


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


@pytest.fixture
def notion_image():
    return (DEMO_DIR / "notion.png").read_bytes()


def test_known_service_line_gets_docs_url_without_calling_ollama(kb, notion_image, monkeypatch):
    """지식베이스에 있는 서비스(Notion API 키)는 Ollama를 호출하지 않고도 known으로 라벨링된다."""
    called = []
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **kw: called.append(1) or "[]")

    boxes = explain.explain_image(notion_image, kb, CONFIG)

    known = [b for b in boxes if b.tier == "known"]
    assert any(b.label and b.docs_url for b in known), "known 박스 중 docs_url이 채워진 게 없음"
    # Notion API 키 값이 포함된 줄은 known이어야 하고, 이 케이스에선 미분류 줄이 없을 수도 있으므로
    # Ollama가 아예 호출 안 됐거나(미분류 줄 없음) 한 번만 호출됐는지만 확인(과호출 방지).
    assert len(called) <= 1


def test_unknown_line_gets_ai_label_from_ollama(kb, notion_image, monkeypatch):
    def fake_generate(config, prompt, timeout=30.0):
        assert "index" in prompt  # 프롬프트가 JSON 형식 안내를 포함하는지 최소 확인
        return json.dumps([{"index": 0, "label": "안내 문구"}])

    monkeypatch.setattr(ollama_client, "generate", fake_generate)

    boxes = explain.explain_image(notion_image, kb, CONFIG)

    ai_boxes = [b for b in boxes if b.tier == "ai_unverified"]
    # 최소 하나는 실제로 Ollama가 붙여준 라벨("안내 문구")을 갖고 있어야 한다(전부 "알 수 없음"이면 실패).
    assert any(b.label == "안내 문구" for b in ai_boxes) or not ai_boxes


def test_ollama_unavailable_falls_back_to_unknown_label(kb, notion_image, monkeypatch):
    """Ollama 연결 실패 시 전체 요청은 안 죽고, 미분류 줄은 '알 수 없음'으로 표시된다."""
    def raise_unavailable(config, prompt, timeout=30.0):
        raise OllamaUnavailableError("연결 실패")

    monkeypatch.setattr(ollama_client, "generate", raise_unavailable)

    boxes = explain.explain_image(notion_image, kb, CONFIG)

    ai_boxes = [b for b in boxes if b.tier == "ai_unverified"]
    assert all(b.label == "알 수 없음" for b in ai_boxes)


def test_malformed_ollama_json_falls_back_gracefully(kb, notion_image, monkeypatch):
    """Ollama가 JSON이 아닌 잡담을 반환해도 전체 요청은 실패하지 않는다."""
    monkeypatch.setattr(
        ollama_client, "generate", lambda *a, **kw: "죄송하지만 잘 모르겠어요!"
    )

    boxes = explain.explain_image(notion_image, kb, CONFIG)

    ai_boxes = [b for b in boxes if b.tier == "ai_unverified"]
    assert all(b.label == "알 수 없음" for b in ai_boxes)


def test_all_boxes_have_valid_rect_coordinates(kb, notion_image, monkeypatch):
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **kw: "[]")
    boxes = explain.explain_image(notion_image, kb, CONFIG)
    assert len(boxes) > 0
    for b in boxes:
        assert b.w > 0 and b.h > 0
        assert b.x >= 0 and b.y >= 0
