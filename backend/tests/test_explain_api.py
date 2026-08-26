# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""설명 기능 엔드포인트 — httpx(certifi/MPL) 회피, 라우트 함수 직접 호출.

explain_image_endpoint 는 async def 라 asyncio.run()으로 직접 실행한다(pytest-asyncio 같은
새 테스트 의존성 추가 없이 — manager-relay/tests/test_main.py 의 raw ASGI 호출 테스트와 같은
정신: 표준 라이브러리만으로 async 코드를 동기 테스트에서 구동한다).
"""
import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from app import main
from app.ocr import _KOREAN_REC_MODEL
from app.ollama_client import OllamaConfig

DEMO_DIR = Path(__file__).parent.parent.parent / "docs" / "demo"

pytestmark = pytest.mark.skipif(
    not _KOREAN_REC_MODEL.exists(),
    reason="OCR 모델 미벤더링 — python backend/scripts/vendor_ocr_models.py 먼저 실행",
)


def test_status_unavailable_when_ollama_config_none(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", None)
    result = main.explain_status()
    assert result.available is False


def test_status_reflects_health_check(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", OllamaConfig("http://x", "m"))
    monkeypatch.setattr(main.ollama_client, "is_available", lambda config: True)
    assert main.explain_status().available is True

    monkeypatch.setattr(main.ollama_client, "is_available", lambda config: False)
    assert main.explain_status().available is False


class _FakeUploadFile:
    def __init__(self, content_type: str, data: bytes):
        self.content_type = content_type
        self._data = data

    async def read(self, max_bytes: int) -> bytes:
        return self._data[:max_bytes]


def test_explain_image_endpoint_503_when_not_configured(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", None)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(main.explain_image_endpoint(image=_FakeUploadFile("image/png", b"fake")))
    assert exc_info.value.status_code == 503


def test_explain_image_endpoint_422_on_non_image(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", OllamaConfig("http://x", "m"))
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(main.explain_image_endpoint(image=_FakeUploadFile("text/plain", b"fake")))
    assert exc_info.value.status_code == 422


def test_explain_image_endpoint_returns_boxes(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", OllamaConfig("http://x", "m"))
    monkeypatch.setattr(main.ollama_client, "generate", lambda *a, **kw: "[]")
    image_bytes = (DEMO_DIR / "notion.png").read_bytes()
    result = asyncio.run(
        main.explain_image_endpoint(image=_FakeUploadFile("image/png", image_bytes))
    )
    assert len(result.boxes) > 0
