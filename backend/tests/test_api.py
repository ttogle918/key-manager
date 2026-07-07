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
    assert r.services == 9
    assert r.credentials == 22


def test_knowledge_endpoint():
    services = knowledge()["services"]
    assert len(services) == 9
    notion = next(s for s in services if s["service"] == "notion")
    api = next(c for c in notion["credentials"] if c["kind"] == "api_key")
    assert api["value_based"] is True
    db = next(c for c in notion["credentials"] if c["kind"] == "database_id")
    assert db["value_based"] is False


def test_knowledge_exposes_guide_help():
    """GUIDE-1: /knowledge 가 발급 도움말(서비스: console_url/steps/prereq, 종류: role/issue_url/docs_url)을 노출."""
    services = knowledge()["services"]
    gcp = next(s for s in services if s["service"] == "gcp")
    # 서비스 단위 도움말
    assert gcp["console_url"] and gcp["console_url"].startswith("https://")
    assert len(gcp["steps"]) >= 2 and gcp["prereq"]
    # 종류 단위 도움말 — 서비스 계정 키는 별도 issue_url(IAM) 보유
    sa = next(c for c in gcp["credentials"] if c["kind"] == "service_account_json")
    assert sa["role"] and sa["docs_url"].startswith("https://")
    assert "iam-admin" in sa["issue_url"]
    # 도움말 미선언 서비스도 필드는 존재(None/[] — 하위호환)
    assert "role" in gcp["credentials"][0] and "console_url" in gcp


def test_knowledge_exposes_security_grade():
    """GUIDE-2: /knowledge 가 노출 등급·유출 피해·보안 팁을 노출."""
    services = knowledge()["services"]
    kakao = next(s for s in services if s["service"] == "kakao")
    admin = next(c for c in kakao["credentials"] if c["kind"] == "admin_key")
    js = next(c for c in kakao["credentials"] if c["kind"] == "javascript_key")
    assert admin["exposure"] == "secret" and admin["impact"]  # 서버 전용 + 피해 문구
    assert js["exposure"] == "public"  # 웹 노출 허용 키
    # 필드는 모든 종류에 존재(하위호환)
    assert "exposure" in js and "security_tip" in admin


def test_analyze():
    resp = analyze_endpoint(AnalyzeRequest(text=f"OPENAI_API_KEY={OPENAI_KEY}"))
    assert resp.count == 1
    assert resp.items[0].official_env_name == "OPENAI_API_KEY"
    assert resp.items[0].confidence == "high"


def test_analyze_empty():
    resp = analyze_endpoint(AnalyzeRequest())
    assert resp.count == 0
