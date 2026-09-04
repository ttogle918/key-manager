# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""설명 기능 엔드포인트 - httpx(certifi/MPL) 회피, 라우트 함수 직접 호출.

explain_image_endpoint 는 async def 라 asyncio.run()으로 직접 실행한다(pytest-asyncio 같은
새 테스트 의존성 추가 없이 - manager-relay/tests/test_main.py 의 raw ASGI 호출 테스트와 같은
정신: 표준 라이브러리만으로 async 코드를 동기 테스트에서 구동한다).
"""
import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from app import main
from app.ocr import _KOREAN_REC_MODEL
from app.ollama_client import OllamaConfig, OllamaUnavailableError

DEMO_DIR = Path(__file__).parent.parent.parent / "docs" / "demo"

pytestmark = pytest.mark.skipif(
    not _KOREAN_REC_MODEL.exists(),
    reason="OCR 모델 미벤더링 - python backend/scripts/vendor_ocr_models.py 먼저 실행",
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


def test_explain_image_endpoint_422_on_generic_explain_failure(monkeypatch):
    """/analyze/image 와 동일하게, OCR 실패 외의 알 수 없는 예외도 422로 친절히 감싼다."""
    monkeypatch.setattr(main, "OLLAMA_CONFIG", OllamaConfig("http://x", "m"))

    def boom(*a, **kw):
        raise RuntimeError("corrupt image")

    monkeypatch.setattr(main.explain, "explain_image", boom)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(main.explain_image_endpoint(image=_FakeUploadFile("image/png", b"fake")))
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "이미지를 읽지 못했어요 - 다른 스크린샷으로 시도해 주세요"


def test_explain_image_endpoint_503_when_ollama_connection_fails(monkeypatch):
    """Ollama 연결 실패(OllamaUnavailableError)는 OCR/이미지 문제와 구분되는 503으로 응답한다."""
    monkeypatch.setattr(main, "OLLAMA_CONFIG", OllamaConfig("http://x", "m"))

    def boom(*a, **kw):
        raise OllamaUnavailableError("연결 실패")

    monkeypatch.setattr(main.explain, "explain_image", boom)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(main.explain_image_endpoint(image=_FakeUploadFile("image/png", b"fake")))
    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "로컬 LLM에 연결할 수 없어요 - Ollama가 실행 중인지 확인하세요"


def test_explain_discoveries_rejects_known_tier(monkeypatch):
    from app.models import ExplainDiscoveryApprove

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            main.explain_discoveries_endpoint(
                ExplainDiscoveryApprove(text="sk-...", label="OpenAI API 키", tier="known", docs_url=None)
            )
        )
    assert exc_info.value.status_code == 422


def test_explain_discoveries_rejects_unknown_label(monkeypatch):
    """확인되지 않은("알 수 없음") 추정은 캐시에 영구 고정될 수 있으므로 저장을 거부한다."""
    from app import explain
    from app.models import ExplainDiscoveryApprove

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            main.explain_discoveries_endpoint(
                ExplainDiscoveryApprove(
                    text="뭔가 알 수 없는 줄", label=explain.UNKNOWN_LABEL,
                    tier="ai_unverified", docs_url=None,
                )
            )
        )
    assert exc_info.value.status_code == 422


def test_explain_discoveries_appends_to_cache(monkeypatch, tmp_path):
    from app import discoveries_repo
    from app.models import ExplainDiscoveryApprove

    cache_path = tmp_path / "local_discoveries.yaml"
    monkeypatch.setattr(main, "DISCOVERIES_PATH", str(cache_path))

    asyncio.run(
        main.explain_discoveries_endpoint(
            ExplainDiscoveryApprove(
                text="API Key: abcdefgh12345678", label="예시 서비스 안내",
                tier="ai_verified", docs_url="https://example.com/docs",
            )
        )
    )

    pattern = discoveries_repo.normalize_pattern("API Key: abcdefgh12345678")
    found = discoveries_repo.find_by_pattern(cache_path, pattern)
    assert found is not None
    assert found["label"] == "예시 서비스 안내"
    assert found["confirmed"] is False
