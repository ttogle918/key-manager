# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 VaultService.sdk_env 등 서비스 레이어 테스트."""
import pytest

from app.vault_session import SdkApprovalPending, VaultLocked, VaultService

MASTER = "correct horse battery staple"


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
