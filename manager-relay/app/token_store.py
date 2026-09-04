# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""확인 대기 중인 이메일 내보내기 요청을 메모리에만 잠깐 보관한다.

DB가 아니다 — 발송 성공(consume) 또는 TTL 만료(자동 스윕)로 반드시 사라진다.
매니저 서버가 재시작되면(예: 서버리스 스케일-투-제로) 대기 중이던 요청은 유실될 수
있으나, 사용자가 다시 요청하면 되므로 이 트레이드오프를 그대로 받아들인다
(docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md 판단 3).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable

DEFAULT_TTL_SECONDS = 15 * 60

# 확인 코드 오입력 허용 횟수. 6자리(백만 분의 1)를 무차별 대입하려면 턱없이 모자란 수이면서,
# 손가락이 미끄러진 사람은 막지 않을 만큼은 된다. 소진하면 토큰째 버린다.
MAX_CODE_ATTEMPTS = 5
CODE_DIGITS = 6


def new_code() -> str:
    """확인 코드 생성. random 이 아니라 secrets 를 쓴다 - 추측되면 그대로 발송 권한이다."""
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


@dataclass
class PendingExport:
    destination_email: str
    bundle: dict
    expires_at: float
    # 코드 원문은 두지 않는다. 앱 화면에 띄우려고 한 번 돌려준 뒤로는 대조만 하면 된다.
    code_hash: str
    attempts_left: int


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

    def issue(self, destination_email: str, bundle: dict) -> tuple[str, str]:
        """(토큰, 확인 코드)를 발급한다. 코드는 여기서만 원문으로 나가고 이후로는 해시만 남는다."""
        token = secrets.token_urlsafe(32)
        code = new_code()
        with self._lock:
            self._sweep_locked()
            self._pending[token] = PendingExport(
                destination_email=destination_email,
                bundle=bundle,
                expires_at=self._clock() + self._ttl,
                code_hash=_hash_code(code),
                attempts_left=MAX_CODE_ATTEMPTS,
            )
        return token, code

    def verify_code(self, token: str, code: str) -> tuple[bool, int]:
        """코드를 대조한다. (성공 여부, 남은 시도 횟수)를 돌려준다.

        틀리면 시도 횟수를 깎고, 다 쓰면 토큰을 버린다 - 무제한 대입을 막는다. 비교는
        compare_digest 로 한다(길이가 같은 해시끼리라 타이밍 차이가 정보가 되지 않도록).
        """
        with self._lock:
            self._sweep_locked()
            entry = self._pending.get(token)
            if entry is None:
                return False, 0
            if hmac.compare_digest(entry.code_hash, _hash_code(code)):
                return True, entry.attempts_left
            entry.attempts_left -= 1
            if entry.attempts_left <= 0:
                del self._pending[token]
                return False, 0
            return False, entry.attempts_left

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
