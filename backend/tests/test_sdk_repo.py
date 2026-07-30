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
    # path는 호출자가 넘긴 원본 문자열 그대로 저장돼야 한다 — 정규화는 내부 매칭용
    # path_norm 컬럼에서만 일어나고, 사용자에게 보이는 값(path)은 절대 변형되지 않는다.
    assert dirs[0]["path"] == "/repo/blog"
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


def test_normalize_path_collapses_equal_inputs():
    """트레일링 슬래시만 다른 두 경로는 정규화 후 같은 값이어야 한다(독립 오라클)."""
    assert sdk_repo._normalize_path("/repo/blog/") == sdk_repo._normalize_path("/repo/blog")


def test_normalize_path_keeps_distinct_inputs_distinct():
    """서로 다른 경로는 정규화 후에도 여전히 달라야 한다(과도한 뭉뚱그림 방지)."""
    assert sdk_repo._normalize_path("/repo/a") != sdk_repo._normalize_path("/repo/b")


def test_is_path_approved_rejects_other_path_in_nonempty_table(conn):
    """허용 목록에 다른 경로가 등록돼 있어도, 등록되지 않은 경로는 여전히 거부돼야 한다
    (빈 테이블에서 그냥 False가 나오는 게 아니라 실제로 값을 구분한다는 증거)."""
    sdk_repo.add_project_dir(conn, "블로그", "/repo/blog", source="manual")
    assert sdk_repo.is_path_approved(conn, "블로그", "/repo/other") is False


def test_connect_backfills_missing_path_norm_column_project_dirs(tmp_path):
    """3차 리뷰 반영: path_norm 컬럼이 없는 구버전(5컬럼) sdk_project_dirs를 가진 vault.db를
    재연결하면, CREATE TABLE IF NOT EXISTS로는 컬럼을 추가할 수 없으므로 connect()가
    ALTER TABLE + 백필로 path_norm을 채워 넣어야 한다.
    """
    path = str(tmp_path / "vault.db")
    old_conn = vault_repo.connect(path)
    vault_repo.init_vault(old_conn, MASTER)
    # "구버전" 상태 시뮬레이션: path_norm 없는 5컬럼 스키마로 되돌린다.
    old_conn.execute("DROP TABLE sdk_project_dirs")
    old_conn.execute(
        """
        CREATE TABLE sdk_project_dirs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project    TEXT NOT NULL,
            path       TEXT NOT NULL,
            source     TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    # add_project_dir()는 이제 path_norm 존재를 전제하므로, raw SQL로 직접 삽입한다.
    old_conn.execute(
        "INSERT INTO sdk_project_dirs (project, path, source, created_at)"
        " VALUES (?,?,?,?)",
        ("블로그", "/repo/blog/", "manual", "2026-01-01T00:00:00+00:00"),
    )
    old_conn.commit()
    old_conn.close()

    new_conn = vault_repo.connect(path)
    try:
        dirs = sdk_repo.list_project_dirs(new_conn, "블로그")
        assert len(dirs) == 1
        assert dirs[0]["path"] == "/repo/blog/"  # 원본 path는 그대로 보존
        # 백필된 path_norm이 실제로 매칭에 쓰일 수 있어야 한다.
        assert sdk_repo.is_path_approved(new_conn, "블로그", "/repo/blog/") is True
    finally:
        new_conn.close()


def test_connect_backfills_missing_path_norm_column_pending_requests(tmp_path):
    """sdk_pending_requests에 대해서도 동일한 컬럼 백필 마이그레이션이 동작해야 한다."""
    path = str(tmp_path / "vault.db")
    old_conn = vault_repo.connect(path)
    vault_repo.init_vault(old_conn, MASTER)
    old_conn.execute("DROP TABLE sdk_pending_requests")
    old_conn.execute(
        """
        CREATE TABLE sdk_pending_requests (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project      TEXT NOT NULL,
            path         TEXT NOT NULL,
            requested_at TEXT NOT NULL
        )
        """
    )
    cur = old_conn.execute(
        "INSERT INTO sdk_pending_requests (project, path, requested_at)"
        " VALUES (?,?,?)",
        ("블로그", "/repo/blog/", "2026-01-01T00:00:00+00:00"),
    )
    old_pending_id = cur.lastrowid
    old_conn.commit()
    old_conn.close()

    new_conn = vault_repo.connect(path)
    try:
        pending = sdk_repo.list_pending_requests(new_conn)
        assert len(pending) == 1
        assert pending[0]["path"] == "/repo/blog/"
        pid = pending[0]["id"]
        assert sdk_repo.get_pending(new_conn, pid)["path"] == "/repo/blog/"
        # path_norm이 실제로 백필됐는지 검증: add_pending_request의 기존 행 조회는
        # path_norm으로 매칭하므로, 컬럼이 없으면 OperationalError가, 백필이 안 됐으면
        # 매칭 실패로 새 행이 생겨 다른 id가 반환된다. 백필이 맞았을 때만 기존 id 그대로 반환.
        assert sdk_repo.add_pending_request(new_conn, "블로그", "/repo/blog/") == old_pending_id
        # approve_pending()이 정상 동작(path_norm이 있어야 add_project_dir 내부 조회가 성공)
        assert sdk_repo.approve_pending(new_conn, pid) is True
        assert sdk_repo.is_path_approved(new_conn, "블로그", "/repo/blog/") is True
    finally:
        new_conn.close()


def test_add_project_dir_preserves_trailing_slash_verbatim(conn):
    """플랫폼 무관 원본 보존 검증(3차 리뷰): normpath는 POSIX·Windows 모두에서
    트레일링 슬래시를 제거하므로, 이 입력은 정규화가 저장 전에 새어 들어가면
    어느 플랫폼에서든 실패한다(기존 "/repo/blog" 테스트는 POSIX에서 공허했다).
    """
    sdk_repo.add_project_dir(conn, "블로그", "/repo/blog/", source="manual")
    dirs = sdk_repo.list_project_dirs(conn, "블로그")
    assert len(dirs) == 1
    assert dirs[0]["path"] == "/repo/blog/"


def test_pending_request_preserves_trailing_slash_verbatim(conn):
    """대기 요청도 path를 원본 그대로 보존해야 한다(플랫폼 무관 검증)."""
    pid = sdk_repo.add_pending_request(conn, "블로그", "/repo/blog/")
    assert sdk_repo.get_pending(conn, pid)["path"] == "/repo/blog/"
    assert sdk_repo.list_pending_requests(conn)[0]["path"] == "/repo/blog/"


def test_approve_pending_preserves_trailing_slash_verbatim(conn):
    """대기→승인 전체 생명주기에서도 원본 path(트레일링 슬래시 포함)가 유지돼야 한다."""
    pending_id = sdk_repo.add_pending_request(conn, "블로그", "/repo/blog/")
    assert sdk_repo.approve_pending(conn, pending_id) is True
    dirs = sdk_repo.list_project_dirs(conn, "블로그")
    assert len(dirs) == 1
    assert dirs[0]["path"] == "/repo/blog/"


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
