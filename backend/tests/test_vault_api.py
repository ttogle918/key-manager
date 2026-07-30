# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""VAULT-2 엔드포인트 상태코드 매핑 테스트. httpx(certifi/MPL) 회피 — 라우트 함수 직접 호출."""
import pytest
from fastapi import HTTPException

from app import main
from app.models import (
    VaultChangePassword,
    VaultEntryCreate,
    VaultEntryUpdate,
    VaultInit,
    VaultPassword,
    VaultRotate,
)
from app.vault_session import VaultService

MASTER = "correct horse battery staple"
DUMMY = "sk-proj-DummyTwoThreeAbcdEfghTwoThree"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """main.VAULT 를 임시 경로의 새 금고로 교체."""
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    monkeypatch.setattr(main, "VAULT", svc)
    return svc


def test_status_uninitialized(vault):
    st = main.vault_status()
    assert st.initialized is False and st.unlocked is False


def test_init_then_status(vault):
    st = main.vault_init(VaultInit(password=MASTER))
    assert st.initialized is True and st.unlocked is True


def test_init_twice_conflict(vault):
    main.vault_init(VaultInit(password=MASTER))
    with pytest.raises(HTTPException) as e:
        main.vault_init(VaultInit(password=MASTER))
    assert e.value.status_code == 409


def test_unlock_wrong_password_401(vault):
    main.vault_init(VaultInit(password=MASTER))
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.vault_unlock(VaultPassword(password="nope"))
    assert e.value.status_code == 401


def test_init_weak_password_rejected(vault):
    """새 금고 생성 시 8자 미만 마스터 비밀번호는 백엔드에서도 거부(방어 심화)."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        VaultInit(password="short")  # 5자 < 8


def test_init_single_char_type_rejected(vault):
    """개인정보보호위원회 비밀번호 작성규칙: 8자 이상이어도 문자 종류가 1개뿐이면 거부."""
    with pytest.raises(HTTPException) as e:
        main.vault_init(VaultInit(password="alllowercase"))
    assert e.value.status_code == 422


def test_init_two_kinds_needs_ten_chars(vault):
    """영문+숫자 2종류 조합이면 10자 미만은 거부, 10자 이상은 통과."""
    with pytest.raises(HTTPException) as e:
        main.vault_init(VaultInit(password="abc12345"))  # 2종류, 8자 < 10
    assert e.value.status_code == 422
    st = main.vault_init(VaultInit(password="abcdefgh12"))  # 2종류, 10자
    assert st.initialized is True


def test_init_three_kinds_eight_chars_ok(vault):
    """영문+숫자+특수문자 3종류 조합이면 8자로도 통과."""
    st = main.vault_init(VaultInit(password="Abcd12!@"))
    assert st.initialized is True


def test_change_password_weak_new_password_rejected(vault):
    main.vault_init(VaultInit(password=MASTER))
    with pytest.raises(HTTPException) as e:
        main.vault_change_password(
            VaultChangePassword(old_password=MASTER, new_password="alllowercase")
        )
    assert e.value.status_code == 422


def test_add_and_get_value_flow(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(
        VaultEntryCreate(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY)
    )
    assert meta.official_name == "OPENAI_API_KEY"
    got = main.vault_get_value(meta.id)
    assert got.value == DUMMY


def test_add_when_locked_401(vault):
    main.vault_init(VaultInit(password=MASTER))
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    assert e.value.status_code == 401


def test_get_value_when_locked_401(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_lock()
    # 잠금 상태: 목록(메타)은 되지만 값은 401
    assert len(main.vault_list()) == 1
    with pytest.raises(HTTPException) as e:
        main.vault_get_value(meta.id)
    assert e.value.status_code == 401


def test_change_password_wrong_old_401(vault):
    main.vault_init(VaultInit(password=MASTER))
    with pytest.raises(HTTPException) as e:
        main.vault_change_password(
            VaultChangePassword(old_password="wrong", new_password="new long password")
        )
    assert e.value.status_code == 401


def test_add_stores_project_memo(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(
        VaultEntryCreate(
            official_name="OPENAI_API_KEY", value=DUMMY, project="블로그", memo="6월 발급"
        )
    )
    assert meta.project == "블로그" and meta.memo == "6월 발급"


def test_update_meta(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    updated = main.vault_update(meta.id, VaultEntryUpdate(project="새프로젝트", memo="메모"))
    assert updated.project == "새프로젝트" and updated.memo == "메모"
    # 값은 여전히 복호화 가능(암호문 불변)
    assert main.vault_get_value(meta.id).value == DUMMY


def test_delete_entry(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_delete(meta.id)
    assert main.vault_list() == []
    with pytest.raises(HTTPException) as e:
        main.vault_get_value(meta.id)
    assert e.value.status_code == 404


def test_delete_when_locked_401(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.vault_delete(meta.id)
    assert e.value.status_code == 401


def test_history_records_register_and_access(vault):
    """등록·열람·복사·내보내기가 감사 이력에 남는다(값 없음)."""
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_get_value(meta.id, event="reveal")
    main.vault_get_value(meta.id, event="copy")
    main.vault_get_value(meta.id, event="export")
    hist = main.vault_history(meta.id)
    events = [h.event for h in hist]  # 최신순
    assert events == [".env 내보내기", "복사", "열람", "등록"]
    # 이력에 실제 값이 들어가지 않는다
    assert all(DUMMY not in h.date and DUMMY not in h.event for h in hist)


def test_history_when_locked_401(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.vault_history(meta.id)
    assert e.value.status_code == 401


def test_rotate_replaces_value_and_logs(vault):
    """값 교체 → 새 값으로 복호화되고, 이력에 '키 교체'가 남는다."""
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    new_value = "sk-proj-RotatedNineEightSevenSix"
    main.vault_rotate(meta.id, VaultRotate(value=new_value))
    assert main.vault_get_value(meta.id).value == new_value  # 옛 값은 폐기됨
    events = [h.event for h in main.vault_history(meta.id)]
    assert "키 교체" in events


def test_rotate_when_locked_401(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.vault_rotate(meta.id, VaultRotate(value="sk-proj-whatever12345678"))
    assert e.value.status_code == 401


def test_rotate_missing_404(vault):
    main.vault_init(VaultInit(password=MASTER))
    with pytest.raises(HTTPException) as e:
        main.vault_rotate(999, VaultRotate(value="sk-proj-whatever12345678"))
    assert e.value.status_code == 404


def test_delete_cascades_access_log(vault):
    """항목 삭제 시 그 감사 이력도 함께 삭제된다(FK CASCADE)."""
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_get_value(meta.id, event="reveal")
    main.vault_delete(meta.id)
    assert main.vault_history(meta.id) == []


# ── TRUST-1: 키 유효성 검증 엔드포인트 ──


def _openai_entry():
    return VaultEntryCreate(
        service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY
    )


def test_verify_active(vault, monkeypatch):
    """유효 키(모킹 200) → active, 감사 이력에 '유효성 검증' 기록(값 없음)."""
    from app import verify as verify_mod

    monkeypatch.setattr(verify_mod, "_http_fetch", lambda *_: 200)
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(_openai_entry())
    res = main.vault_verify(meta.id)
    assert res.status == "active"
    events = [h.event for h in main.vault_history(meta.id)]
    assert "유효성 검증" in events
    assert all(DUMMY not in h.event for h in main.vault_history(meta.id))


def test_verify_invalid(vault, monkeypatch):
    """폐기·오타 키(모킹 401) → invalid."""
    from app import verify as verify_mod

    monkeypatch.setattr(verify_mod, "_http_fetch", lambda *_: 401)
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(_openai_entry())
    assert main.vault_verify(meta.id).status == "invalid"


def test_verify_network_error_unknown(vault, monkeypatch):
    """네트워크 오류 → unknown(키 문제로 단정하지 않음)."""
    from app import verify as verify_mod

    def boom(*_):
        raise OSError("연결 실패")

    monkeypatch.setattr(verify_mod, "_http_fetch", boom)
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(_openai_entry())
    assert main.vault_verify(meta.id).status == "unknown"


def test_verify_unsupported_service_no_network(vault, monkeypatch):
    """검증 엔드포인트가 없는 서비스(kakao)는 호출 없이 unsupported."""
    from app import verify as verify_mod

    def must_not_call(*_):
        raise AssertionError("검증 엔드포인트 없는 서비스에서 네트워크 호출 발생")

    monkeypatch.setattr(verify_mod, "_http_fetch", must_not_call)
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(
        VaultEntryCreate(
            service="kakao", kind="rest_api_key", official_name="KAKAO_REST_API_KEY", value=DUMMY
        )
    )
    assert main.vault_verify(meta.id).status == "unsupported"


def test_verify_when_locked_401(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(_openai_entry())
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.vault_verify(meta.id)
    assert e.value.status_code == 401


def test_verify_missing_404(vault):
    main.vault_init(VaultInit(password=MASTER))
    with pytest.raises(HTTPException) as e:
        main.vault_verify(999)
    assert e.value.status_code == 404
