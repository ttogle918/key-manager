# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""엔드포인트 상태코드/부수효과 테스트. httpx(certifi/MPL) 회피 — 라우트 함수 직접 호출."""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import main
from app.mailer import MailSendError
from app.models import SyncRequestBody
from app.rate_limit import RateLimiter
from app.token_store import TokenStore

# backend/app/vault_repo.py 의 실제 BUNDLE_FORMAT("keylens-vault")과 일치해야 SyncRequestBody
# 의 형식 검증(Fix 6)을 통과한다.
BUNDLE = {"format": "keylens-vault", "version": 1, "entries": []}


@pytest.fixture
def relay(monkeypatch):
    """main 의 전역 상태를 매 테스트마다 새로 교체 — 테스트 간 간섭 방지."""
    monkeypatch.setattr(main, "STORE", TokenStore())
    monkeypatch.setattr(main, "RATE_PER_EMAIL", RateLimiter(limit=3, window_seconds=3600))
    monkeypatch.setattr(main, "RATE_PER_IP", RateLimiter(limit=10, window_seconds=3600))
    sent = {"confirm": [], "bundle": []}

    def fake_confirm(config, destination_email, confirm_url):
        sent["confirm"].append((destination_email, confirm_url))

    def fake_bundle(config, destination_email, bundle_json):
        sent["bundle"].append((destination_email, bundle_json))

    monkeypatch.setattr(main, "send_confirm_email", fake_confirm)
    monkeypatch.setattr(main, "send_bundle_email", fake_bundle)
    return sent


def test_sync_request_issues_token_and_sends_confirm_email(relay):
    result = main.sync_request(
        SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
    )
    assert result == {"requested": True}
    assert len(relay["confirm"]) == 1
    dest, confirm_url = relay["confirm"][0]
    assert dest == "dest@example.com"
    assert "/sync/confirm?token=" in confirm_url


def test_sync_request_rate_limited_by_email(relay):
    for _ in range(3):
        main.sync_request(
            SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
        )
    with pytest.raises(HTTPException) as exc_info:
        main.sync_request(
            SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="9.9.9.9"
        )
    assert exc_info.value.status_code == 429


def test_sync_request_confirm_email_failure_raises_502(relay, monkeypatch):
    def failing_send(config, destination_email, confirm_url):
        raise MailSendError("boom")

    monkeypatch.setattr(main, "send_confirm_email", failing_send)
    with pytest.raises(HTTPException) as exc_info:
        main.sync_request(
            SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
        )
    assert exc_info.value.status_code == 502


def test_sync_confirm_valid_token_sends_bundle_and_consumes(relay):
    main.sync_request(
        SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
    )
    _, confirm_url = relay["confirm"][0]
    token = confirm_url.split("token=")[1]

    response = main.sync_confirm(token)
    assert response.status_code == 200
    body = response.body.decode() if isinstance(response.body, bytes) else response.body
    assert "발송" in body
    assert len(relay["bundle"]) == 1
    dest, bundle_json = relay["bundle"][0]
    assert dest == "dest@example.com"
    assert '"format": "keylens-vault"' in bundle_json or '"format":"keylens-vault"' in bundle_json

    # 1회용 소진 — 같은 토큰 재사용은 410(안내 HTML)
    retry = main.sync_confirm(token)
    assert retry.status_code == 410
    retry_body = retry.body.decode() if isinstance(retry.body, bytes) else retry.body
    assert "만료" in retry_body


def test_sync_confirm_unknown_token_returns_410_html(relay):
    response = main.sync_confirm("nonexistent-token")
    assert response.status_code == 410
    body = response.body.decode() if isinstance(response.body, bytes) else response.body
    assert "만료" in body


def test_sync_confirm_bundle_send_failure_keeps_token_for_retry(relay, monkeypatch):
    main.sync_request(
        SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
    )
    _, confirm_url = relay["confirm"][0]
    token = confirm_url.split("token=")[1]

    def failing_send(config, destination_email, bundle_json):
        raise MailSendError("boom")

    monkeypatch.setattr(main, "send_bundle_email", failing_send)
    response = main.sync_confirm(token)
    assert response.status_code == 502
    body = response.body.decode() if isinstance(response.body, bytes) else response.body
    assert "발송" in body

    # 소진되지 않았으므로 재시도(다음 클릭)는 여전히 유효한 토큰으로 처리돼야 함
    monkeypatch.setattr(main, "send_bundle_email", lambda c, d, b: relay["bundle"].append((d, b)))
    main.sync_confirm(token)
    assert len(relay["bundle"]) == 1


def test_client_ip_prefers_x_forwarded_for(relay):
    """리버스 프록시(Cloud Run 등) 뒤에서는 request.client.host 대신 X-Forwarded-For 의
    첫 값을 실제 클라이언트 IP로 써야 한다 — 그렇지 않으면 전체 사용자가 프록시의 IP
    하나로 뭉쳐 IP별 요율 제한이 사실상 전역 제한이 되어버린다."""

    class FakeClient:
        host = "10.0.0.1"  # 프록시 자신의 IP

    class FakeRequest:
        def __init__(self, headers):
            self.headers = headers
            self.client = FakeClient()

    request_with_xff = FakeRequest({"x-forwarded-for": "203.0.113.5, 10.0.0.1"})
    assert main._client_ip(request_with_xff) == "203.0.113.5"

    request_without_xff = FakeRequest({})
    assert main._client_ip(request_without_xff) == "10.0.0.1"


def test_sync_request_rejects_invalid_bundle_format(relay):
    with pytest.raises(ValidationError):
        SyncRequestBody(
            destination_email="dest@example.com",
            bundle={"format": "not-keylens-vault", "version": 1, "entries": []},
        )


def test_sync_request_rejects_missing_bundle_format(relay):
    with pytest.raises(ValidationError):
        SyncRequestBody(destination_email="dest@example.com", bundle={"version": 1, "entries": []})


def test_reject_oversized_requests_middleware_returns_413():
    """ASGI 미들웨어는 이 파일의 다른 테스트처럼 라우트 함수를 직접 호출하는 방식으로는
    검증할 수 없다 — call_next 를 흉내 낸 최소 더미로 미들웨어 함수 자체를 직접 호출한다.

    다만 이 테스트는 미들웨어 함수 자체의 로직(임계값 판단, 라우트 가드)만 검증할 뿐,
    앱에 실제로 어떤 순서로 등록됐는지는 전혀 건드리지 않는다 — CORSMiddleware와의 등록
    순서 버그(Finding 1) 같은 클래스의 문제는 이 테스트로는 절대 못 잡는다. 그래서 아래
    test_oversized_request_through_real_app_has_cors_header 가 실제 app 객체를 raw ASGI로
    구동해 그 부분까지 검증한다."""
    import asyncio

    class FakeRequest:
        method = "POST"

        class url:
            path = "/sync/request"

        headers = {"content-length": str(main.MAX_REQUEST_BYTES + 1)}

    async def call_next_should_not_be_called(request):  # pragma: no cover - 방어용
        raise AssertionError("본문 크기 초과 시 call_next 가 호출되면 안 됨")

    response = asyncio.run(
        main._reject_oversized_requests(FakeRequest(), call_next_should_not_be_called)
    )
    assert response.status_code == 413


async def _call_asgi_app(app, *, method, path, headers, body=b""):
    """httpx(certifi/MPL) 없이 실제 ASGI 앱(미들웨어 스택 포함)을 stdlib만으로 구동한다.

    FastAPI/Starlette 의 `app`은 평범한 ASGI 콜러블(`async def app(scope, receive, send)`)이라
    실제 소켓이나 TestClient 없이도 scope/receive/send 를 손수 만들어 직접 호출할 수 있다.
    이렇게 하면 라우트 함수 하나만 부르는 게 아니라 등록된 미들웨어 체인 전체(CORS 포함)를
    실제로 통과하므로, 미들웨어 "등록 순서" 버그까지 잡아낼 수 있다.
    """
    body_sent = False

    async def receive():
        nonlocal body_sent
        if not body_sent:
            body_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    messages = []

    async def send(message):
        messages.append(message)

    if "?" in path:
        path, _, query_string = path.partition("?")
    else:
        query_string = ""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": query_string.encode(),
        "root_path": "",
        "scheme": "http",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in headers
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    await app(scope, receive, send)

    start = next(m for m in messages if m["type"] == "http.response.start")
    body_chunks = [m.get("body", b"") for m in messages if m["type"] == "http.response.body"]
    return {
        "status": start["status"],
        "headers": start["headers"],  # 리스트[(lower-case bytes, bytes)] — ASGI 스펙
        "body": b"".join(body_chunks),
    }


def _get_header(headers, name):
    """ASGI 응답 헤더(소문자 바이트 튜플 리스트)에서 대소문자 구분 없이 값을 찾는다."""
    target = name.lower().encode()
    for k, v in headers:
        if k.lower() == target:
            return v
    return None


def test_oversized_request_through_real_app_has_cors_header(relay):
    """Finding 1/2 회귀 테스트 — 실제 FastAPI `app` 객체를 raw ASGI로 구동해, 용량 초과 시
    반환되는 413 응답에 CORS 헤더(access-control-allow-origin)가 실제로 붙는지 검증한다.

    기존 test_reject_oversized_requests_middleware_returns_413 은 미들웨어 함수를 직접
    호출할 뿐이라 등록 순서(CORSMiddleware가 이 미들웨어를 감싸는지)를 전혀 검증하지
    못했다 — 이 테스트가 바로 그 등록 순서를 검증한다. (main.py 를 되돌려 CORSMiddleware를
    _reject_oversized_requests 보다 먼저 등록하도록 만들면 이 테스트가 실패하는 것으로
    수동 확인함.)
    """
    import asyncio

    oversized = str(main.MAX_REQUEST_BYTES + 1)
    result = asyncio.run(
        _call_asgi_app(
            main.app,
            method="POST",
            path="/sync/request",
            headers=[
                ("content-length", oversized),
                ("origin", "http://localhost:5173"),
                ("content-type", "application/json"),
            ],
            body=b"{}",
        )
    )
    assert result["status"] == 413
    cors_header = _get_header(result["headers"], "access-control-allow-origin")
    assert cors_header is not None, (
        "413 응답에 CORS 헤더가 없음 — 크기 제한 미들웨어가 CORSMiddleware보다 바깥에서 "
        "등록돼 있을 가능성이 있음(Finding 1)"
    )


def test_normal_request_through_real_app_is_not_rejected_by_size_guard(relay):
    """라우트 스코프 가드가 실제 앱 배선에서도 여전히 정상 동작하는지 확인한다 —
    크기 제한 미들웨어는 POST /sync/request 에만 적용돼야 하고, 다른 경로/메서드의
    보통 크기 요청은 통과시켜야 한다."""
    import asyncio

    result = asyncio.run(
        _call_asgi_app(
            main.app,
            method="GET",
            path="/sync/confirm?token=nonexistent-token",
            headers=[("origin", "http://localhost:5173")],
            body=b"",
        )
    )
    # 존재하지 않는 토큰이므로 410(만료 안내 HTML)이 기대값 — 413(용량 초과)만 아니면 됨,
    # 즉 크기 제한 미들웨어가 이 경로를 잘못 가로채지 않았다는 뜻.
    assert result["status"] != 413
    assert result["status"] == 410
