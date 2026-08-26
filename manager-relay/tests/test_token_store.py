# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""토큰 저장소 — 발급→조회→소진, TTL 만료를 검증한다. DB 없이 메모리 dict만 쓴다."""
from app.token_store import TokenStore


def test_issue_then_peek_returns_entry():
    store = TokenStore()
    token = store.issue("user@example.com", {"format": "klvault", "entries": []})
    entry = store.peek(token)
    assert entry is not None
    assert entry.destination_email == "user@example.com"
    assert entry.bundle == {"format": "klvault", "entries": []}


def test_peek_does_not_consume():
    store = TokenStore()
    token = store.issue("user@example.com", {})
    store.peek(token)
    assert store.peek(token) is not None  # 두 번째 조회에도 여전히 존재


def test_consume_removes_entry():
    store = TokenStore()
    token = store.issue("user@example.com", {})
    store.consume(token)
    assert store.peek(token) is None


def test_unknown_token_returns_none():
    store = TokenStore()
    assert store.peek("nonexistent-token") is None


def test_expired_token_returns_none():
    now = [1000.0]
    store = TokenStore(ttl_seconds=60, clock=lambda: now[0])
    token = store.issue("user@example.com", {})
    now[0] += 61  # TTL 경과
    assert store.peek(token) is None


def test_not_yet_expired_token_still_valid():
    now = [1000.0]
    store = TokenStore(ttl_seconds=60, clock=lambda: now[0])
    token = store.issue("user@example.com", {})
    now[0] += 59  # TTL 직전
    assert store.peek(token) is not None
