# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 /sdk/* 엔드포인트 상태코드 매핑 테스트 — 라우트 함수 직접 호출."""
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


def test_sdk_add_dir_after_approval_refetches_source(vault):
    """sdk_add_dir는 자체 합성 dict가 아니라 list_project_dirs 재조회 결과를 반환해야 한다.

    같은 (project, path)가 이미 승인(source="approved")으로 등록돼 있으면,
    VaultService.add_project_dir가 반환하는 합성 dict는 source="manual"을 주장하지만
    (그리고 created_at도 없다), 라우트는 반드시 재조회한 실제 row를 사용해야 한다.
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
