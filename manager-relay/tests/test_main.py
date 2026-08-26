# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""엔드포인트 상태코드/부수효과 테스트. httpx(certifi/MPL) 회피 — 라우트 함수 직접 호출."""
import pytest
from fastapi import HTTPException

from app import main
from app.mailer import MailSendError
from app.models import SyncRequestBody
from app.rate_limit import RateLimiter
from app.token_store import TokenStore

BUNDLE = {"format": "klvault", "version": 1, "entries": []}


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

    html = main.sync_confirm(token)
    assert "발송" in html
    assert len(relay["bundle"]) == 1
    dest, bundle_json = relay["bundle"][0]
    assert dest == "dest@example.com"
    assert '"format": "klvault"' in bundle_json or '"format":"klvault"' in bundle_json

    # 1회용 소진 — 같은 토큰 재사용은 410
    with pytest.raises(HTTPException) as exc_info:
        main.sync_confirm(token)
    assert exc_info.value.status_code == 410


def test_sync_confirm_unknown_token_returns_410(relay):
    with pytest.raises(HTTPException) as exc_info:
        main.sync_confirm("nonexistent-token")
    assert exc_info.value.status_code == 410


def test_sync_confirm_bundle_send_failure_keeps_token_for_retry(relay, monkeypatch):
    main.sync_request(
        SyncRequestBody(destination_email="dest@example.com", bundle=BUNDLE), client_ip="1.2.3.4"
    )
    _, confirm_url = relay["confirm"][0]
    token = confirm_url.split("token=")[1]

    def failing_send(config, destination_email, bundle_json):
        raise MailSendError("boom")

    monkeypatch.setattr(main, "send_bundle_email", failing_send)
    with pytest.raises(HTTPException) as exc_info:
        main.sync_confirm(token)
    assert exc_info.value.status_code == 502

    # 소진되지 않았으므로 재시도(다음 클릭)는 여전히 유효한 토큰으로 처리돼야 함
    monkeypatch.setattr(main, "send_bundle_email", lambda c, d, b: relay["bundle"].append((d, b)))
    main.sync_confirm(token)
    assert len(relay["bundle"]) == 1
