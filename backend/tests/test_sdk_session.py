# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 VaultService.sdk_env 등 서비스 레이어 테스트."""
import pytest

from app.vault_session import SdkApprovalPending, VaultLocked, VaultService

MASTER = "correct horse battery staple"


class Clock:
    """제어 가능한 시계 — 자동잠금 갱신 여부 테스트용(test_vault_session.py와 동일 패턴)."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, secs: float) -> None:
        self.t += secs


@pytest.fixture
def vault(tmp_path):
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    svc.init(MASTER)
    return svc


def test_sdk_env_locked_raises(tmp_path):
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    svc.init(MASTER)
    svc.lock()
    with pytest.raises(VaultLocked):
        svc.sdk_env("블로그", "/repo/blog")


def test_sdk_env_unapproved_path_raises_pending(vault):
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    assert len(vault.list_pending()) == 1
    assert vault.list_pending()[0]["project"] == "블로그"


def test_sdk_env_second_unapproved_request_is_idempotent(vault):
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    assert len(vault.list_pending()) == 1


def test_sdk_env_approved_path_returns_values(vault):
    vault.add_entry(
        service="notion", kind="api_key", official_name="NOTION_API_KEY",
        value="secret_dummy", project="블로그",
    )
    vault.add_project_dir("블로그", "/repo/blog")
    env = vault.sdk_env("블로그", "/repo/blog")
    assert env == {"NOTION_API_KEY": "secret_dummy"}


def test_sdk_env_denied_path_stays_unapproved(vault):
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    pending_id = vault.list_pending()[0]["id"]
    assert vault.deny_pending(pending_id) is True
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")


def test_sdk_env_approve_pending_grants_future_access(vault):
    vault.add_entry(
        service="openai", kind="api_key", official_name="OPENAI_API_KEY",
        value="sk-dummy", project="블로그",
    )
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    pending_id = vault.list_pending()[0]["id"]
    assert vault.approve_pending(pending_id) is True
    env = vault.sdk_env("블로그", "/repo/blog")
    assert env == {"OPENAI_API_KEY": "sk-dummy"}


def test_sdk_env_logs_audit_history(vault):
    entry_id = vault.add_entry(
        service="openai", kind="api_key", official_name="OPENAI_API_KEY",
        value="sk-dummy", project="블로그",
    )
    vault.add_project_dir("블로그", "/repo/blog")
    vault.sdk_env("블로그", "/repo/blog")
    history = vault.history(entry_id)
    assert any(h["event"] == "SDK 조회" for h in history)


def test_remove_project_dir_and_relist(vault):
    created = vault.add_project_dir("블로그", "/repo/blog")
    assert vault.remove_project_dir("블로그", created["id"]) is True
    assert vault.list_project_dirs("블로그") == []


def test_list_projects_delegates_to_repo(vault):
    vault.add_entry(
        service=None, kind=None, official_name="OPENAI_API_KEY", value="sk-dummy",
        project="사이드",
    )
    projects = vault.list_projects()
    assert any(p["project"] == "사이드" for p in projects)


def test_sdk_env_does_not_refresh_auto_lock_timer(tmp_path):
    """RUNTIME-1 3차 리뷰: SDK 조회(sdk_env)는 자동 잠금 타이머를 갱신하지 않는다.

    human-initiated 행동(add_entry 등)은 _require_key(refresh=True)로 타이머를 갱신하지만,
    sdk_env는 _require_key(refresh=False)를 쓴다 — 자리를 비운 사용자가 백그라운드에서
    계속 load_env()를 호출하는 개발 서버 때문에 자동 잠금이 무한정 미뤄지면 안 되기 때문.
    이 테스트는 test_vault_session.py::test_activity_resets_auto_lock(사람 행동은 갱신함)과
    대조된다 — 여기서는 반대로 "갱신 안 됨(결국 잠김)"을 확인한다.
    """
    clock = Clock()
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60, clock=clock)
    svc.init(MASTER)  # last_activity = 1000 (clock 시작값)
    svc.add_entry(
        service="openai", kind="api_key", official_name="OPENAI_API_KEY",
        value="sk-dummy", project="블로그",
    )  # human 행동 — _require_key(refresh=True) → last_activity 유지(1000, 같은 tick)
    svc.add_project_dir("블로그", "/repo/blog")  # 값을 안 다뤄 _require_key 자체를 안 씀

    clock.advance(59)  # last_activity(1000) 기준 59s < 60 → 아직 잠기지 않음
    env = svc.sdk_env("블로그", "/repo/blog")  # 승인된 경로 → 성공
    assert env == {"OPENAI_API_KEY": "sk-dummy"}

    clock.advance(2)  # 원래 last_activity(1000) 기준 61s 경과 → 잠겨야 함
    # sdk_env가 타이머를 갱신했다면 last_activity=1059가 되어 여기서는 아직 2s밖에
    # 안 지나 잠기지 않았을 것 — 잠겨 있다는 건 sdk_env가 갱신하지 않았다는 증거.
    assert svc.status()["unlocked"] is False
    with pytest.raises(VaultLocked):
        svc.sdk_env("블로그", "/repo/blog")


def test_readonly_and_narrowing_management_works_while_locked(vault):
    """값을 다루지 않고 **권한을 넓히지도 않는** 관리 메서드는 잠금 상태에서도 동작해야 한다.

    조회(list_*)와 권한을 좁히는 쪽(remove_project_dir·deny_pending)이 대상이다.
    권한을 넓히는 쪽(add_project_dir·approve_pending)은 아래 별도 테스트에서
    잠금 해제를 요구하는지 확인한다 - 예전엔 그쪽도 잠긴 채로 통과해서, 아무 로컬
    프로세스나 자기 경로를 스스로 허용 목록에 넣을 수 있었다.
    """
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/pending-a")
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/pending-b")
    pending_ids = [p["id"] for p in vault.list_pending()]
    assert len(pending_ids) == 2

    created = vault.add_project_dir("블로그", "/repo/blog")  # 아직 잠금 해제 상태

    vault.lock()
    assert vault.status()["unlocked"] is False

    # 조회 - 잠긴 상태에서도 가능(값은 나오지 않는다)
    assert any(d["id"] == created["id"] for d in vault.list_project_dirs("블로그"))
    assert isinstance(vault.list_projects(), list)
    assert len(vault.list_pending()) == 2

    # 권한을 좁히는 쪽 - 잠긴 상태에서도 가능(안전한 방향)
    assert vault.remove_project_dir("블로그", created["id"]) is True
    assert vault.deny_pending(pending_ids[1]) is True
    assert len(vault.list_pending()) == 1


def test_granting_management_requires_unlock(vault):
    """권한 부여(디렉토리 등록·대기 승인)는 잠금 해제를 요구한다.

    회귀 방지: 이게 열려 있으면 승인 대기 화면이 장식이 된다 - 악성 로컬 프로세스가
    자기 디렉토리를 등록하거나 자기 요청을 스스로 승인한 뒤, 사용자가 다음번 잠금을
    해제하는 순간 값을 받아갈 수 있었다.
    """
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    pending_id = vault.list_pending()[0]["id"]

    vault.lock()

    with pytest.raises(VaultLocked):
        vault.add_project_dir("블로그", "/evil/dir")
    with pytest.raises(VaultLocked):
        vault.approve_pending(pending_id)

    # 잠긴 동안 아무 권한도 생기지 않았어야 한다
    vault.unlock(MASTER)
    assert vault.list_project_dirs("블로그") == []
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/evil/dir")


def test_set_pending_hook_called_once_for_new_request(vault):
    calls = []
    vault.set_pending_hook(lambda project, path: calls.append((project, path)))
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    assert calls == [("블로그", "/repo/blog")]


def test_set_pending_hook_not_called_again_for_duplicate_request(vault):
    calls = []
    vault.set_pending_hook(lambda project, path: calls.append((project, path)))
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    assert len(calls) == 1


def test_pending_hook_defaults_to_noop(tmp_path):
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    svc.init(MASTER)
    with pytest.raises(SdkApprovalPending):
        svc.sdk_env("블로그", "/repo/blog")  # 훅 미등록이어도 예외 없이 정상 동작(no-op)


def test_pending_hook_not_called_when_path_already_approved(vault):
    calls = []
    vault.set_pending_hook(lambda project, path: calls.append((project, path)))
    vault.add_project_dir("블로그", "/repo/blog")
    env = vault.sdk_env("블로그", "/repo/blog")
    assert env == {}
    assert calls == []


def test_set_pending_hook_can_be_cleared(vault):
    calls = []
    vault.set_pending_hook(lambda project, path: calls.append((project, path)))
    vault.set_pending_hook(None)
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    assert calls == []
