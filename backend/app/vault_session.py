# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""VAULT-2 인증 게이트 — 금고 세션(메모리 키) + 자동 잠금 + 실패 지연 (SPEC 6장).

유도된 키는 이 프로세스 메모리에만 있고, 잠금(수동/타이머)되면 폐기된다.
값 조회는 잠금 해제 상태에서만 가능하고, 잠금 상태에서는 **메타데이터만** 보인다.
연속 인증 실패 시 백오프 지연으로 무차별 대입을 늦춘다.

로컬 단일 사용자(127.0.0.1) 전제 — 전역 단일 세션. `clock` 주입으로 자동잠금을 테스트에서 시뮬레이트한다.
"""
from __future__ import annotations

import time
from typing import Callable

from . import crypto, vault_repo

AUTO_LOCK_SECONDS = 300  # 5분 무활동 시 자동 잠금 (기본값)
FAIL_FREE = 2  # 이 횟수까지의 연속 실패는 지연 없음 (기본값)
MAX_DELAY = 30  # 실패 지연 상한(초) (기본값)


class VaultLocked(Exception):
    """잠금 상태 — 값 접근 전 인증 필요."""


class VaultRateLimited(Exception):
    """연속 실패로 잠시 인증 시도 차단."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"인증 시도가 많습니다 — {retry_after}s 후 다시 시도하세요")
        self.retry_after = retry_after


class VaultService:
    def __init__(
        self,
        db_path: str,
        auto_lock_seconds: int = AUTO_LOCK_SECONDS,
        fail_free: int = FAIL_FREE,
        max_delay: int = MAX_DELAY,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.db_path = db_path
        self.auto_lock_seconds = auto_lock_seconds
        self.fail_free = fail_free
        self.max_delay = max_delay
        self._clock = clock
        self._key: bytes | None = None
        self._last_activity = 0.0
        self._fail_count = 0
        self._locked_until = 0.0

    @classmethod
    def from_env(cls, db_path: str, env: dict[str, str] | None = None) -> "VaultService":
        """환경변수로 잠금 정책을 구성한다(미설정 시 기본값). 로컬 개인 도구라 각자 튜닝 가능."""
        import os

        e = env if env is not None else os.environ

        def _int(key: str, default: int) -> int:
            try:
                v = int(e[key])
                return v if v > 0 else default
            except (KeyError, ValueError):
                return default

        return cls(
            db_path,
            auto_lock_seconds=_int("KEYLENS_AUTOLOCK_SECONDS", AUTO_LOCK_SECONDS),
            fail_free=_int("KEYLENS_AUTH_FREE_ATTEMPTS", FAIL_FREE),
            max_delay=_int("KEYLENS_AUTH_MAX_DELAY_SECONDS", MAX_DELAY),
        )

    # ── 상태 ──
    def _conn(self):
        return vault_repo.connect(self.db_path)

    def is_initialized(self) -> bool:
        conn = self._conn()
        try:
            return vault_repo.is_initialized(conn)
        finally:
            conn.close()

    def _is_unlocked(self) -> bool:
        if self._key is None:
            return False
        if self._clock() - self._last_activity > self.auto_lock_seconds:
            self.lock()  # 자동 잠금
            return False
        return True

    def status(self) -> dict:
        return {"initialized": self.is_initialized(), "unlocked": self._is_unlocked()}

    # ── 세션 ──
    def init(self, password: str) -> None:
        conn = self._conn()
        try:
            key = vault_repo.init_vault(conn, password)
        finally:
            conn.close()
        self._set_unlocked(key)

    def unlock(self, password: str) -> None:
        now = self._clock()
        if now < self._locked_until:
            raise VaultRateLimited(round(self._locked_until - now, 1))
        conn = self._conn()
        try:
            key = vault_repo.unlock(conn, password)  # 오답이면 crypto.DecryptError
        except crypto.DecryptError:
            self._fail_count += 1
            over = self._fail_count - self.fail_free
            if over > 0:
                self._locked_until = now + min(2 ** (over - 1), self.max_delay)
            raise
        finally:
            conn.close()
        self._fail_count = 0
        self._locked_until = 0.0
        self._set_unlocked(key)

    def lock(self) -> None:
        self._key = None

    def _set_unlocked(self, key: bytes) -> None:
        self._key = key
        self._last_activity = self._clock()

    def _require_key(self) -> bytes:
        if not self._is_unlocked():
            raise VaultLocked()
        self._last_activity = self._clock()
        assert self._key is not None
        return self._key

    # ── 항목 ──
    def add_entry(
        self,
        *,
        service: str | None,
        kind: str | None,
        official_name: str | None,
        value: str,
        label: str | None = None,
        project: str | None = None,
        memo: str | None = None,
        expires_at: str | None = None,
    ) -> int:
        key = self._require_key()
        conn = self._conn()
        try:
            return vault_repo.add_entry(
                conn, key, service=service, kind=kind, official_name=official_name,
                value=value, label=label, project=project, memo=memo, expires_at=expires_at,
            )
        finally:
            conn.close()

    def update_meta(
        self,
        entry_id: int,
        *,
        project: str | None = None,
        memo: str | None = None,
        expires_at: str | None = None,
    ) -> bool:
        self._require_key()
        conn = self._conn()
        try:
            return vault_repo.update_meta(
                conn, entry_id, project=project, memo=memo, expires_at=expires_at
            )
        finally:
            conn.close()

    def delete_entry(self, entry_id: int) -> bool:
        self._require_key()
        conn = self._conn()
        try:
            return vault_repo.delete_entry(conn, entry_id)
        finally:
            conn.close()

    def list_entries(self) -> list[dict]:
        """메타데이터만 반환 — 잠금 상태에서도 안전(값 복호화 없음)."""
        if not self.is_initialized():
            return []
        conn = self._conn()
        try:
            return vault_repo.list_entries(conn)
        finally:
            conn.close()

    def get_value(self, entry_id: int, event: str = "reveal") -> str:
        """평문 값 복호화 — 잠금 상태면 VaultLocked. 접근을 감사 이력에 기록(event: reveal/copy/export)."""
        key = self._require_key()
        conn = self._conn()
        try:
            value = vault_repo.get_value(conn, key, entry_id)
            vault_repo.log_access(conn, entry_id, event)  # 복호화 성공 시에만 기록
            return value
        finally:
            conn.close()

    def history(self, entry_id: int) -> list[dict]:
        """항목의 감사 이력(등록·열람·복사·내보내기). 인증 상태에서만 조회 가능."""
        self._require_key()
        conn = self._conn()
        try:
            return vault_repo.access_history(conn, entry_id)
        finally:
            conn.close()

    def change_password(self, old_password: str, new_password: str) -> None:
        conn = self._conn()
        try:
            vault_repo.change_password(conn, old_password, new_password)
        finally:
            conn.close()
        self.lock()  # 변경 후 재인증 요구
