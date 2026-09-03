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


def test_add_without_project_defaults_to_today(vault, monkeypatch):
    """프로젝트 미지정 저장 — 등록일(UTC)이 실제 project 값으로 채워진다(keylens-env 컬렉션명으로도 씀)."""
    monkeypatch.setattr(main, "_today", lambda: "2026-08-27")
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    assert meta.project == "2026-08-27"


def test_add_with_blank_project_also_defaults_to_today(vault, monkeypatch):
    """공백만 있는 project도 미지정과 동일하게 취급."""
    monkeypatch.setattr(main, "_today", lambda: "2026-08-27")
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY, project="   "))
    assert meta.project == "2026-08-27"


def test_update_clearing_project_falls_back_to_created_at_date(vault):
    """PATCH로 project를 비우면 '오늘'이 아니라 그 항목의 등록일(created_at)로 되돌아간다."""
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(
        VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY, project="블로그")
    )
    updated = main.vault_update(meta.id, VaultEntryUpdate(project=""))
    assert updated.project == meta.created_at[:10]


def test_update_meta(vault):
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    updated = main.vault_update(meta.id, VaultEntryUpdate(project="새프로젝트", memo="메모"))
    assert updated.project == "새프로젝트" and updated.memo == "메모"
    # 값은 여전히 복호화 가능(암호문 불변)
    assert main.vault_get_value(meta.id).value == DUMMY


def test_reset_wrong_password_401_data_intact(vault):
    """틀린 비밀번호로 reset 시도 → 401, 기존 항목 무손상."""
    main.vault_init(VaultInit(password=MASTER))
    main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    with pytest.raises(HTTPException) as e:
        main.vault_reset(VaultPassword(password="wrong password"))
    assert e.value.status_code == 401
    assert len(main.vault_list()) == 1


def test_reset_uninitialized_vault_409(vault):
    """애초에 초기화 안 된 금고에 reset 시도 → 409."""
    with pytest.raises(HTTPException) as e:
        main.vault_reset(VaultPassword(password=MASTER))
    assert e.value.status_code == 409


def test_reset_succeeds_and_uninitializes(vault):
    """올바른 비밀번호로 reset → 성공 후 vault_status가 미초기화를 반환, 세션도 잠김."""
    main.vault_init(VaultInit(password=MASTER))
    main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    result = main.vault_reset(VaultPassword(password=MASTER))
    assert result.initialized is False
    assert result.unlocked is False
    st = main.vault_status()
    assert st.initialized is False


def test_reset_works_while_locked(vault):
    """세션이 실제로 잠긴 상태에서도 비밀번호만으로 reset이 동작해야 한다(판단 2의 핵심 주장)."""
    main.vault_init(VaultInit(password=MASTER))
    main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    vault.lock()
    result = main.vault_reset(VaultPassword(password=MASTER))
    assert result.initialized is False


def test_reset_clears_access_log(vault):
    """reset은 감사 이력(access_log)도 완전히 비운다 — DELETE FROM entries의 FK CASCADE에
    기대지 않고 access_log 테이블 자체를 직접 조회해 검증한다(entries가 지워지면 CASCADE로도
    비워지므로, access_log에 대한 명시적 DELETE가 빠져도 통과해버리는 회귀를 못 잡는 문제가
    있었음 — 브랜치 최종 리뷰에서 발견)."""
    import sqlite3

    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    assert main.vault_history(meta.id) != []  # "register" 이벤트가 남아 있음
    main.vault_reset(VaultPassword(password=MASTER))

    conn = sqlite3.connect(vault.db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM access_log").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_reset_purges_plaintext_metadata_from_db_file(vault):
    """DELETE만으로는 SQLite 프리리스트에 평문 메타데이터가 남는다 — VACUUM으로 실제 제거되는지
    raw .db 파일 바이트를 직접 검사해 확인한다(API 응답 검사로는 이 회귀를 못 잡는다)."""
    main.vault_init(VaultInit(password=MASTER))
    distinctive = "Xk9-VeryDistinctiveProjectName-Zq7"
    main.vault_add(
        VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY, project=distinctive)
    )
    main.vault_reset(VaultPassword(password=MASTER))

    raw = open(vault.db_path, "rb").read()
    assert distinctive.encode("utf-8") not in raw


def test_reset_then_reinit_works(vault):
    """reset 후 같은(또는 다른) 비밀번호로 다시 init 가능 — 파일이 아니라 데이터만 지워짐."""
    main.vault_init(VaultInit(password=MASTER))
    main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_reset(VaultPassword(password=MASTER))
    st = main.vault_init(VaultInit(password=MASTER))
    assert st.initialized is True
    assert main.vault_list() == []  # 이전 항목 완전히 사라짐


def test_reset_clears_sdk_project_dirs(vault):
    """SDK 디렉토리 사전등록(RUNTIME-1)도 reset 대상 — 공용 PC에 이전 사용자 승인 흔적이 안 남아야 함."""
    main.vault_init(VaultInit(password=MASTER))
    vault.add_project_dir("블로그", "/home/user/blog")
    assert vault.list_project_dirs("블로그") != []
    main.vault_reset(VaultPassword(password=MASTER))
    main.vault_init(VaultInit(password=MASTER))
    assert vault.list_project_dirs("블로그") == []


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


# ── RUNTIME-4: 보관함 항목의 서비스 재지정 ──────────────────────────────────────
#
# 분류기가 모든 걸 맞힐 수는 없어서 "미지정"으로 남는 항목이 생긴다. 사용자가 직접
# 올바른 서비스로 옮길 수 있어야 한다. 값의 AAD 는 official_name 뿐이라 서비스 변경에는
# 재암호화가 필요 없다 — 그래서 평문 메타데이터 수정으로 끝난다.


def _unclassified(vault_svc):
    """서비스 미지정 상태의 항목 하나를 만든다(.env 가져오기의 DB_HOST 같은 줄)."""
    main.vault_init(VaultInit(password=MASTER))
    return main.vault_add(
        VaultEntryCreate(official_name="DB_HOST", value="localhost-dummy-value")
    )


def test_assign_service_to_unclassified_entry(vault):
    meta = _unclassified(vault)
    assert meta.service is None

    updated = main.vault_update(
        meta.id, VaultEntryUpdate(service="github", kind="personal_access_token")
    )
    assert updated.service == "github"
    assert updated.kind == "personal_access_token"
    # 라벨은 지식베이스가 정한다(클라이언트가 보낸 값을 그대로 믿지 않는다)
    assert updated.label == "Personal Access Token"


def test_service_change_does_not_touch_the_value(vault):
    """재암호화 없이 메타만 바뀐다 — 값은 그대로 복호화된다."""
    meta = _unclassified(vault)
    main.vault_update(meta.id, VaultEntryUpdate(service="github", kind="personal_access_token"))
    assert main.vault_get_value(meta.id).value == "localhost-dummy-value"


def test_service_change_keeps_the_user_chosen_name(vault):
    """official_name 은 그대로 — 그게 이 기능의 약속이고, 바꾸려면 재암호화가 필요하다."""
    meta = _unclassified(vault)
    updated = main.vault_update(meta.id, VaultEntryUpdate(service="github", kind="personal_access_token"))
    assert updated.official_name == "DB_HOST"


def test_can_clear_service_back_to_unclassified(vault):
    meta = _unclassified(vault)
    main.vault_update(meta.id, VaultEntryUpdate(service="github", kind="personal_access_token"))
    cleared = main.vault_update(meta.id, VaultEntryUpdate(service=None, kind=None))
    assert cleared.service is None and cleared.kind is None and cleared.label is None


def test_unknown_service_kind_pair_rejected(vault):
    """지식베이스에 없는 조합은 422 — 저장되면 유효성 검증이 영영 unsupported 가 된다."""
    meta = _unclassified(vault)
    for service, kind in [("github", "no_such_kind"), ("no_such_service", "personal_access_token")]:
        with pytest.raises(HTTPException) as e:
            main.vault_update(meta.id, VaultEntryUpdate(service=service, kind=kind))
        assert e.value.status_code == 422
    assert main.vault_list()[0].service is None  # 아무것도 안 바뀌었다


def test_service_without_kind_rejected(vault):
    """한쪽만 바꾸면 지식베이스에 없는 조합이 된다."""
    meta = _unclassified(vault)
    with pytest.raises(HTTPException) as e:
        main.vault_update(meta.id, VaultEntryUpdate(service="github"))
    assert e.value.status_code == 422


def test_editing_project_alone_preserves_service(vault):
    """**회귀 방지**: 컬렉션만 고치는 요청이 서비스 분류를 지우면 안 된다.

    PATCH 는 '보낸 필드만' 수정한다. 이게 깨지면 사용자가 컬렉션 이름을 고치는 순간
    애써 지정한 서비스가 조용히 날아간다.
    """
    meta = _unclassified(vault)
    main.vault_update(meta.id, VaultEntryUpdate(service="github", kind="personal_access_token"))
    updated = main.vault_update(meta.id, VaultEntryUpdate(project="새컬렉션"))
    assert updated.project == "새컬렉션"
    assert updated.service == "github" and updated.kind == "personal_access_token"


def test_editing_service_alone_preserves_memo_and_project(vault):
    """반대 방향도 마찬가지 — 서비스만 바꿔도 메모·컬렉션이 남는다."""
    meta = _unclassified(vault)
    main.vault_update(meta.id, VaultEntryUpdate(project="블로그", memo="메모다"))
    updated = main.vault_update(meta.id, VaultEntryUpdate(service="github", kind="personal_access_token"))
    assert updated.project == "블로그" and updated.memo == "메모다"


def test_empty_patch_rejected(vault):
    meta = _unclassified(vault)
    with pytest.raises(HTTPException) as e:
        main.vault_update(meta.id, VaultEntryUpdate())
    assert e.value.status_code == 422


def test_partial_update_semantics_over_json(vault):
    """**와이어 계약**: 실제 요청은 JSON 으로 오므로 그 경로에서 '생략'과 '명시적 null' 이
    구분되는지 확인한다. 파이썬에서 VaultEntryUpdate(...) 로 만드는 것만 검증하면
    FastAPI 가 dict 로 만드는 실제 경로를 놓친다.
    """
    meta = _unclassified(vault)
    main.vault_update(meta.id, VaultEntryUpdate(service="github", kind="personal_access_token"))

    # 생략 → 건드리지 않음
    only_project = VaultEntryUpdate.model_validate({"project": "블로그"})
    assert only_project.model_fields_set == {"project"}
    updated = main.vault_update(meta.id, only_project)
    assert updated.service == "github"  # 살아남았다

    # 명시적 null → 비우기
    clear = VaultEntryUpdate.model_validate({"service": None, "kind": None})
    assert clear.model_fields_set == {"service", "kind"}
    updated = main.vault_update(meta.id, clear)
    assert updated.service is None
    assert updated.project == "블로그"  # 컬렉션은 그대로
