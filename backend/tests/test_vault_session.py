# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""VAULT-2 세션/인증 테스트 (SPEC 6장 AC). clock 주입으로 시간 경과를 시뮬레이트. 값은 더미."""
import pytest

from app import crypto
from app.vault_session import VaultLocked, VaultRateLimited, VaultService

MASTER = "correct horse battery staple"
DUMMY = "sk-proj-DummyTwoThreeAbcdEfghTwoThree"


class Clock:
    """제어 가능한 시계 — 자동잠금/지연 테스트용."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, secs: float) -> None:
        self.t += secs


@pytest.fixture
def svc(tmp_path):
    clock = Clock()
    s = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60, clock=clock)
    s.init(MASTER)  # 초기화 = 잠금 해제 상태
    return s, clock


def test_init_unlocks_and_roundtrip(svc):
    s, _ = svc
    assert s.status() == {"initialized": True, "unlocked": True}
    eid = s.add_entry(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY)
    assert s.get_value(eid) == DUMMY


def test_locked_value_access_denied(svc):
    """🧪 잠금 상태에서 값 요청 → 거부 + 인증 유도."""
    s, _ = svc
    eid = s.add_entry(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY)
    s.lock()
    assert s.status()["unlocked"] is False
    with pytest.raises(VaultLocked):
        s.get_value(eid)


def test_list_metadata_visible_when_locked(svc):
    """잠금 상태에서도 메타데이터는 보인다(값 없음)."""
    s, _ = svc
    s.add_entry(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY, label="API Key")
    s.lock()
    items = s.list_entries()
    assert len(items) == 1 and items[0]["official_name"] == "OPENAI_API_KEY"
    assert "value" not in items[0]


def test_auto_lock_after_timeout(svc):
    """✅ 자동 잠금 타이머 동작 — 무활동 시간 초과 후 값 접근 거부."""
    s, clock = svc
    eid = s.add_entry(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY)
    clock.advance(61)  # auto_lock_seconds=60 초과
    assert s.status()["unlocked"] is False
    with pytest.raises(VaultLocked):
        s.get_value(eid)


def test_activity_resets_auto_lock(svc):
    """활동이 있으면 자동잠금 타이머가 갱신된다."""
    s, clock = svc
    eid = s.add_entry(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY)
    clock.advance(40)
    assert s.get_value(eid) == DUMMY  # 활동 → last_activity 갱신
    clock.advance(40)  # 마지막 활동 이후 40s (< 60) → 여전히 해제
    assert s.get_value(eid) == DUMMY


def test_wrong_password_backoff(svc):
    """연속 실패 시 지연(백오프) — 처음 2회는 지연 없고, 이후 RateLimited."""
    s, clock = svc
    s.lock()
    for _ in range(3):  # _FAIL_FREE=2 → 3번째 실패에서 지연 발생
        with pytest.raises(crypto.DecryptError):
            s.unlock("wrong")
    # 이제 즉시 재시도하면 RateLimited(정답이어도 차단)
    with pytest.raises(VaultRateLimited):
        s.unlock(MASTER)
    clock.advance(31)  # 지연 경과
    s.unlock(MASTER)  # 이제 정답 통과
    assert s.status()["unlocked"] is True


def test_successful_unlock_resets_failcount(svc):
    s, _ = svc
    s.lock()
    with pytest.raises(crypto.DecryptError):
        s.unlock("wrong")
    s.unlock(MASTER)
    assert s.status()["unlocked"] is True


def test_change_password_locks_and_reencrypts(svc):
    s, _ = svc
    eid = s.add_entry(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY)
    new_master = "a whole new master phrase"
    s.change_password(MASTER, new_master)
    assert s.status()["unlocked"] is False  # 변경 후 재인증 요구
    with pytest.raises(crypto.DecryptError):
        s.unlock(MASTER)
    s.unlock(new_master)
    assert s.get_value(eid) == DUMMY
