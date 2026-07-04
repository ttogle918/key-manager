# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""API 엔드포인트 테스트.

TestClient(httpx→certifi/MPL-2.0)를 피하려고 라우트 함수를 직접 호출한다.
FastAPI 래핑 계층은 얇으므로 로직·모델·지식베이스 로딩은 이걸로 충분히 검증된다.
HTTP 통합은 `uvicorn` 기동 후 수동 스모크로 확인한다 (README 참고).
"""
from app.main import analyze_endpoint, health, knowledge
from app.models import AnalyzeRequest

OPENAI_KEY = "sk-proj-" + "a" * 20


def test_health():
    r = health()
    assert r.status == "ok"
    assert r.services == 5
    assert r.credentials == 12


def test_knowledge_endpoint():
    services = knowledge()["services"]
    assert len(services) == 5
    notion = next(s for s in services if s["service"] == "notion")
    api = next(c for c in notion["credentials"] if c["kind"] == "api_key")
    assert api["value_based"] is True
    db = next(c for c in notion["credentials"] if c["kind"] == "database_id")
    assert db["value_based"] is False


def test_analyze():
    resp = analyze_endpoint(AnalyzeRequest(text=f"OPENAI_API_KEY={OPENAI_KEY}"))
    assert resp.count == 1
    assert resp.items[0].official_env_name == "OPENAI_API_KEY"
    assert resp.items[0].confidence == "high"


def test_analyze_empty():
    resp = analyze_endpoint(AnalyzeRequest())
    assert resp.count == 0
