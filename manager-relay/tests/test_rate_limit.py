# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""고정 윈도우 요율 제한 — dest_email/IP별로 시간당 요청 횟수를 독립 집계한다."""
import pytest

from app.rate_limit import RateLimitExceeded, RateLimiter


def test_allows_up_to_limit():
    limiter = RateLimiter(limit=3, window_seconds=3600)
    for _ in range(3):
        limiter.check("user@example.com")  # 예외 없이 통과해야 함


def test_raises_after_limit_exceeded():
    limiter = RateLimiter(limit=3, window_seconds=3600)
    for _ in range(3):
        limiter.check("user@example.com")
    with pytest.raises(RateLimitExceeded):
        limiter.check("user@example.com")


def test_different_keys_independent():
    limiter = RateLimiter(limit=1, window_seconds=3600)
    limiter.check("a@example.com")
    limiter.check("b@example.com")  # 다른 키라 별도 한도 — 예외 없어야 함


def test_window_resets_after_elapsed_time():
    now = [1000.0]
    limiter = RateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])
    limiter.check("user@example.com")
    now[0] += 61  # 윈도우 경과
    limiter.check("user@example.com")  # 다시 허용돼야 함


def test_retry_after_reported_on_exceeded():
    now = [1000.0]
    limiter = RateLimiter(limit=1, window_seconds=60, clock=lambda: now[0])
    limiter.check("user@example.com")
    now[0] += 10
    with pytest.raises(RateLimitExceeded) as exc_info:
        limiter.check("user@example.com")
    assert 45 <= exc_info.value.retry_after <= 50


def test_refund_returns_the_most_recent_slot():
    limiter = RateLimiter(limit=2, window_seconds=3600)
    limiter.check("a@example.com")
    limiter.check("a@example.com")

    limiter.refund("a@example.com")

    limiter.check("a@example.com")  # 환불된 자리를 다시 쓸 수 있어야 한다
    with pytest.raises(RateLimitExceeded):
        limiter.check("a@example.com")


def test_refund_on_an_unseen_key_is_harmless():
    """없는 키를 환불해도 조용히 넘어간다 - 방어적 호출이 예외를 만들면 안 된다."""
    RateLimiter(limit=1).refund("never-seen@example.com")
