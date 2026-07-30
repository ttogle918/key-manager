# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 sdk_repo 단위 테스트 — 프로젝트 디렉토리·승인 대기열 CRUD."""
import pytest

from app import sdk_repo, vault_repo

MASTER = "correct horse battery staple"


@pytest.fixture
def conn(tmp_path):
    c = vault_repo.connect(str(tmp_path / "vault.db"))
    vault_repo.init_vault(c, MASTER)
    yield c
    c.close()


def test_add_and_list_project_dir(conn):
    sdk_repo.add_project_dir(conn, "블로그", "/repo/blog", source="manual")
    dirs = sdk_repo.list_project_dirs(conn, "블로그")
    assert len(dirs) == 1
    # 저장 시 경로가 정규화된다(구분자/대소문자 통일) — 리터럴이 아닌 정규화 결과와 비교.
    assert dirs[0]["path"] == sdk_repo._normalize_path("/repo/blog")
    assert dirs[0]["source"] == "manual"


def test_add_project_dir_idempotent(conn):
    id1 = sdk_repo.add_project_dir(conn, "블로그", "/repo/blog", source="manual")
    id2 = sdk_repo.add_project_dir(conn, "블로그", "/repo/blog", source="manual")
    assert id1 == id2
    assert len(sdk_repo.list_project_dirs(conn, "블로그")) == 1


def test_remove_project_dir_only_matching_project(conn):
    dir_id = sdk_repo.add_project_dir(conn, "블로그", "/repo/blog", source="manual")
    assert sdk_repo.remove_project_dir(conn, "다른프로젝트", dir_id) is False
    assert sdk_repo.remove_project_dir(conn, "블로그", dir_id) is True
    assert sdk_repo.list_project_dirs(conn, "블로그") == []


def test_is_path_approved(conn):
    assert sdk_repo.is_path_approved(conn, "블로그", "/repo/blog") is False
    sdk_repo.add_project_dir(conn, "블로그", "/repo/blog", source="manual")
    assert sdk_repo.is_path_approved(conn, "블로그", "/repo/blog") is True


def test_pending_request_lifecycle(conn):
    pid = sdk_repo.add_pending_request(conn, "블로그", "/repo/blog")
    assert len(sdk_repo.list_pending_requests(conn)) == 1
    assert sdk_repo.get_pending(conn, pid)["project"] == "블로그"

    assert sdk_repo.approve_pending(conn, pid) is True
    assert sdk_repo.list_pending_requests(conn) == []
    assert sdk_repo.is_path_approved(conn, "블로그", "/repo/blog") is True


def test_pending_request_idempotent(conn):
    id1 = sdk_repo.add_pending_request(conn, "블로그", "/repo/blog")
    id2 = sdk_repo.add_pending_request(conn, "블로그", "/repo/blog")
    assert id1 == id2


def test_deny_pending_does_not_approve(conn):
    pid = sdk_repo.add_pending_request(conn, "블로그", "/repo/blog")
    assert sdk_repo.deny_pending(conn, pid) is True
    assert sdk_repo.list_pending_requests(conn) == []
    assert sdk_repo.is_path_approved(conn, "블로그", "/repo/blog") is False


def test_approve_unknown_pending_returns_false(conn):
    assert sdk_repo.approve_pending(conn, 9999) is False


def test_connect_recreates_missing_sdk_tables(tmp_path):
    """리뷰 반영: 기존(구버전) vault.db를 재연결하면 신규 SDK 테이블이 자동 생성된다.

    이 기능 이전에 만들어진 vault.db는 sdk_project_dirs/sdk_pending_requests 테이블이
    없다. init_vault()는 "이미 초기화된 금고"에서 재실행되지 않으므로, connect()가
    재연결 시점에 누락된 테이블을 채워 넣어야 한다(마이그레이션).
    """
    path = str(tmp_path / "vault.db")
    old_conn = vault_repo.connect(path)
    vault_repo.init_vault(old_conn, MASTER)
    # "구버전" vault.db를 시뮬레이션: 이 기능이 추가되기 전 상태로 되돌린다.
    old_conn.execute("DROP TABLE sdk_project_dirs")
    old_conn.execute("DROP TABLE sdk_pending_requests")
    old_conn.commit()
    old_conn.close()

    new_conn = vault_repo.connect(path)
    try:
        # 예외 없이 동작 + 빈 목록을 반환해야 한다(테이블이 재생성됐다는 증거).
        assert sdk_repo.list_project_dirs(new_conn, "블로그") == []
    finally:
        new_conn.close()


def test_is_path_approved_normalizes_trailing_slash(conn):
    """트레일링 슬래시 유무는 같은 경로로 취급돼야 한다(보안 허용목록 비교의 견고성)."""
    sdk_repo.add_project_dir(conn, "블로그", "/repo/blog/", source="manual")
    assert sdk_repo.is_path_approved(conn, "블로그", "/repo/blog") is True


def test_add_project_dir_idempotent_under_normalization(conn):
    """트레일링 슬래시 차이만 있는 두 경로는 같은 id로 합쳐져야 한다(idempotent)."""
    id1 = sdk_repo.add_project_dir(conn, "블로그", "/repo/blog", source="manual")
    id2 = sdk_repo.add_project_dir(conn, "블로그", "/repo/blog/", source="manual")
    assert id1 == id2
    assert len(sdk_repo.list_project_dirs(conn, "블로그")) == 1


def test_list_sdk_projects_groups_by_project(conn):
    key = vault_repo.unlock(conn, MASTER)
    vault_repo.add_entry(
        conn, key, service="notion", kind="api_key", official_name="NOTION_API_KEY",
        value="secret_dummy", project="블로그",
    )
    vault_repo.add_entry(
        conn, key, service="openai", kind="api_key", official_name="OPENAI_API_KEY",
        value="sk-dummy", project="블로그",
    )
    vault_repo.add_entry(
        conn, key, service="github", kind="api_key", official_name="GITHUB_TOKEN",
        value="ghp_dummy", project=None,
    )
    projects = sdk_repo.list_sdk_projects(conn)
    assert projects == [{"project": "블로그", "key_count": 2}]
