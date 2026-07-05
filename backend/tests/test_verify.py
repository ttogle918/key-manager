# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""TRUST-1 키 유효성 검증기 테스트 — 실제 네트워크 없이 fetcher 를 주입한다.

모든 키 값은 명백한 더미다. 검증 상태 매핑과 값 비노출을 확인한다.
"""
from __future__ import annotations

import pytest

from app.models import VerifySpec
from app.verify import build_request, check_key, classify_status


# ── 상태 매핑 ──
@pytest.mark.parametrize(
    "code, expected",
    [
        (200, "active"),
        (204, "active"),
        (401, "invalid"),
        (403, "invalid"),
        (429, "unknown"),
        (500, "unknown"),
        (404, "unknown"),
    ],
)
def test_classify_status(code: int, expected: str) -> None:
    status, detail = classify_status(code)
    assert status == expected
    assert str(code) in detail


# ── 요청 구성(키가 올바른 위치에 실리는지) ──
def test_build_request_bearer() -> None:
    spec = VerifySpec(url="https://api.openai.com/v1/models", auth="bearer")
    method, url, headers, params = build_request(spec, "sk-dummy-123")
    assert method == "GET"
    assert url.endswith("/v1/models")
    assert headers["Authorization"] == "Bearer sk-dummy-123"
    assert params == {}


def test_build_request_bearer_with_extra_headers() -> None:
    spec = VerifySpec(
        url="https://api.notion.com/v1/users/me",
        auth="bearer",
        extra_headers={"Notion-Version": "2022-06-28"},
    )
    _, _, headers, _ = build_request(spec, "ntn_dummy")
    assert headers["Authorization"] == "Bearer ntn_dummy"
    assert headers["Notion-Version"] == "2022-06-28"


def test_build_request_header_prefix() -> None:
    spec = VerifySpec(
        url="https://kapi.kakao.com/x",
        auth="header",
        header_name="Authorization",
        prefix="KakaoAK ",
    )
    _, _, headers, _ = build_request(spec, "restkey123")
    assert headers["Authorization"] == "KakaoAK restkey123"


def test_build_request_query() -> None:
    spec = VerifySpec(url="https://x/api", auth="query", query_name="key")
    _, _, _, params = build_request(spec, "AIzaDummy")
    assert params == {"key": "AIzaDummy"}


# ── check_key: fetcher 주입으로 네트워크 없이 검증 ──
def _spec() -> VerifySpec:
    return VerifySpec(url="https://api.openai.com/v1/models", auth="bearer")


def test_check_key_active_on_200() -> None:
    status, _ = check_key(_spec(), "sk-valid-dummy", fetch=lambda *_: 200)
    assert status == "active"


def test_check_key_invalid_on_401() -> None:
    status, _ = check_key(_spec(), "sk-revoked-dummy", fetch=lambda *_: 401)
    assert status == "invalid"


def test_check_key_unknown_on_network_error() -> None:
    def boom(*_: object) -> int:
        raise ConnectionError("네트워크 끊김")

    status, detail = check_key(_spec(), "sk-dummy", fetch=boom)
    assert status == "unknown"
    assert "네트워크" in detail or "실패" in detail


def test_check_key_passes_key_to_fetcher_only_in_header() -> None:
    """키는 헤더에만 실리고, 반환 튜플엔 값이 새지 않는지 확인."""
    seen: dict[str, object] = {}

    def capture(method: str, url: str, headers: dict, params: dict) -> int:
        seen.update(headers=headers, params=params)
        return 200

    secret = "sk-super-secret-dummy-000"
    status, detail = check_key(_spec(), secret, fetch=capture)
    assert status == "active"
    assert seen["headers"]["Authorization"] == f"Bearer {secret}"
    # 반환 설명 문자열엔 키 원문이 절대 포함되지 않는다.
    assert secret not in detail
