# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""확인 대기 중인 이메일 내보내기 요청을 메모리에만 잠깐 보관한다.

DB가 아니다 — 발송 성공(consume) 또는 TTL 만료(자동 스윕)로 반드시 사라진다.
매니저 서버가 재시작되면(예: 서버리스 스케일-투-제로) 대기 중이던 요청은 유실될 수
있으나, 사용자가 다시 요청하면 되므로 이 트레이드오프를 그대로 받아들인다
(docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md 판단 3).
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable

DEFAULT_TTL_SECONDS = 15 * 60


@dataclass
class PendingExport:
    destination_email: str
    bundle: dict
    expires_at: float


class TokenStore:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._pending: dict[str, PendingExport] = {}

    def issue(self, destination_email: str, bundle: dict) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._sweep_locked()
            self._pending[token] = PendingExport(
                destination_email=destination_email,
                bundle=bundle,
                expires_at=self._clock() + self._ttl,
            )
        return token

    def peek(self, token: str) -> PendingExport | None:
        """유효하면(존재+미만료) 반환한다 — 소진하지 않는다(발송 실패 시 재시도용)."""
        with self._lock:
            self._sweep_locked()
            return self._pending.get(token)

    def consume(self, token: str) -> None:
        """발송 성공 후 1회용으로 소진한다. 없는 토큰이어도 조용히 무시한다."""
        with self._lock:
            self._pending.pop(token, None)

    def _sweep_locked(self) -> None:
        now = self._clock()
        expired = [t for t, e in self._pending.items() if e.expires_at <= now]
        for t in expired:
            del self._pending[t]
