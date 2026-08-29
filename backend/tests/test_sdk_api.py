# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 /sdk/* 엔드포인트 상태코드 매핑 + 응답 값 테스트 — 라우트 함수 직접 호출."""
import pytest
from fastapi import HTTPException

from app import main
from app.models import SdkAddDirRequest, SdkEnvRequest, VaultEntryCreate, VaultInit
from app.vault_session import VaultService

MASTER = "correct horse battery staple"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    monkeypatch.setattr(main, "VAULT", svc)
    main.vault_init(VaultInit(password=MASTER))
    return svc


def test_sdk_env_unapproved_returns_403(vault):
    with pytest.raises(HTTPException) as e:
        main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    assert e.value.status_code == 403


def test_sdk_env_locked_returns_401(vault):
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    assert e.value.status_code == 401


def test_sdk_add_dir_then_env_succeeds(vault):
    main.vault_add(
        VaultEntryCreate(
            service="notion", kind="api_key", official_name="NOTION_API_KEY",
            value="secret_dummy", project="블로그",
        )
    )
    main.sdk_add_dir("블로그", SdkAddDirRequest(path="/repo/blog"))
    res = main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    assert res.values == {"NOTION_API_KEY": "secret_dummy"}


def test_sdk_pending_list_approve_flow(vault):
    with pytest.raises(HTTPException):
        main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    pending = main.sdk_list_pending()
    assert len(pending) == 1
    result = main.sdk_approve_pending(pending[0].id)
    assert result == {"approved": True}
    res = main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    assert res.values == {}


def test_sdk_deny_pending_keeps_blocked(vault):
    with pytest.raises(HTTPException):
        main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    pending = main.sdk_list_pending()
    result = main.sdk_deny_pending(pending[0].id)
    assert result == {"denied": True}
    with pytest.raises(HTTPException) as e:
        main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    assert e.value.status_code == 403


def test_sdk_approve_unknown_pending_404(vault):
    with pytest.raises(HTTPException) as e:
        main.sdk_approve_pending(9999)
    assert e.value.status_code == 404


def test_sdk_remove_dir_unknown_404(vault):
    with pytest.raises(HTTPException) as e:
        main.sdk_remove_dir("블로그", 9999)
    assert e.value.status_code == 404


def test_sdk_list_projects_reflects_entries(vault):
    main.vault_add(
        VaultEntryCreate(official_name="OPENAI_API_KEY", value="sk-dummy", project="사이드프로젝트")
    )
    projects = main.sdk_list_projects()
    assert any(p.project == "사이드프로젝트" and p.key_count == 1 for p in projects)


def test_sdk_add_dir_after_approval_returns_actual_stored_source(vault):
    """VaultService.add_project_dir는 자체 합성 dict가 아니라 실제 저장된 행을 반환해야 한다.

    같은 (project, path)가 이미 승인(source="approved")으로 등록돼 있으면, 호출자가 넘긴
    인자로 합성한 dict는 source="manual"을 잘못 주장하게 된다(그리고 created_at도 없다) —
    서비스 레이어가 삽입 후 실제 행을 재조회해서 돌려줘야 한다(라우트는 그 값을 그대로 씀).
    """
    with pytest.raises(HTTPException) as e:
        main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    assert e.value.status_code == 403
    pending = main.sdk_list_pending()
    assert len(pending) == 1
    result = main.sdk_approve_pending(pending[0].id)
    assert result == {"approved": True}

    added = main.sdk_add_dir("블로그", SdkAddDirRequest(path="/repo/blog"))
    assert added.source == "approved"


def test_sdk_list_dirs_returns_added_directory(vault):
    main.sdk_add_dir("블로그", SdkAddDirRequest(path="/repo/blog"))
    dirs = main.sdk_list_dirs("블로그")
    assert any(d.path == "/repo/blog" for d in dirs)


def test_sdk_remove_dir_success_path(vault):
    added = main.sdk_add_dir("블로그", SdkAddDirRequest(path="/repo/blog"))
    result = main.sdk_remove_dir("블로그", added.id)
    assert result == {"removed": True}
    dirs = main.sdk_list_dirs("블로그")
    assert all(d.id != added.id for d in dirs)


# ── 회귀: 승인 게이트를 로컬 프로세스가 스스로 우회하던 문제 ──
# 발단: 디렉토리 등록·대기 요청 승인이 잠금 상태에서도 인증 없이 통과해서, 아무 로컬
# 프로세스나 자기 경로를 스스로 허용 목록에 넣고 다음 잠금 해제 때 값을 받아갈 수 있었다.
# 권한을 넓히는 쪽은 잠금 해제를 요구하고, 좁히는 쪽은 잠긴 상태에서도 열어 둔다.


def test_add_dir_requires_unlock(vault):
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.sdk_add_dir("블로그", SdkAddDirRequest(path="/evil/dir"))
    assert e.value.status_code == 401


def test_add_dir_while_locked_does_not_grant_access(vault):
    """우회 시나리오 전체: 잠긴 동안 등록 시도 -> 해제 후에도 여전히 미승인이어야 한다."""
    main.vault_add(
        VaultEntryCreate(official_name="OPENAI_API_KEY", value="sk-dummy", project="블로그")
    )
    main.vault_lock()
    with pytest.raises(HTTPException):
        main.sdk_add_dir("블로그", SdkAddDirRequest(path="/evil/dir"))

    vault.unlock(MASTER)
    with pytest.raises(HTTPException) as e:
        main.sdk_env(SdkEnvRequest(project="블로그", path="/evil/dir"))
    assert e.value.status_code == 403  # 여전히 승인 대기 - 값이 나가지 않는다


def test_approve_pending_requires_unlock(vault):
    with pytest.raises(HTTPException):
        main.sdk_env(SdkEnvRequest(project="블로그", path="/repo/blog"))
    pending_id = main.sdk_list_pending()[0].id

    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.sdk_approve_pending(pending_id)
    assert e.value.status_code == 401


def test_deny_and_remove_still_work_while_locked(vault):
    """권한을 좁히는 쪽은 잠긴 상태에서도 되어야 한다(안전한 방향)."""
    main.sdk_add_dir("블로그", SdkAddDirRequest(path="/repo/blog"))
    dir_id = main.sdk_list_dirs("블로그")[0].id
    with pytest.raises(HTTPException):
        main.sdk_env(SdkEnvRequest(project="블로그", path="/other"))
    pending_id = main.sdk_list_pending()[0].id

    main.vault_lock()
    assert main.sdk_remove_dir("블로그", dir_id) == {"removed": True}
    assert main.sdk_deny_pending(pending_id) == {"denied": True}
