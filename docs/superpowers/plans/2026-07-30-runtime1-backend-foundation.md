<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# RUNTIME-1 백엔드 기반(SDK 접근 관리) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `keylens-env`(RUNTIME-1) SDK가 필요로 하는 백엔드 기반 — 프로젝트별 허용 디렉토리 관리, 승인 대기열, 값 조회(env 병합), 감사 로그 연동 — 을 구현한다. 이 플랜은 4개 하위 계획 중 1번째(백엔드 데이터 모델+API)이며, 프론트 설정 화면·`keylens-env` 패키지 자체·데스크톱 알림은 별도 플랜에서 이 위에 얹는다.

**Architecture:** 기존 `vault_repo.py`(SQLite 스키마·쿼리) / `vault_session.py`(`VaultService`, 세션·인증 게이트) / `models.py`(Pydantic) / `main.py`(FastAPI 라우트) 4계층 구조를 그대로 따른다. 새 책임(프로젝트-디렉토리 허용목록, 승인 대기열, env 값 병합)은 새 모듈 `backend/app/sdk_repo.py`에 담고, `VaultService`가 기존 `_require_key()`/`_conn()` 세션 상태를 재사용해 이를 감싼다. 스키마는 기존 `vault_repo._SCHEMA`에 테이블만 추가한다(단일 소스 유지).

**Tech Stack:** Python 3.11+, FastAPI, 표준 라이브러리 `sqlite3`(신규 의존성 없음). 테스트는 `pytest`로 라우트 함수를 직접 호출한다(httpx 미사용 — 기존 `test_vault_api.py` 관례, certifi/MPL 회피).

## Global Constraints

- 새 런타임 의존성 추가 금지 — 이 플랜은 표준 라이브러리 + 기존 모듈만 사용한다.
- 모든 새 파일 맨 위에 SPDX 헤더 2줄: `# SPDX-FileCopyrightText: 2026 [Your Name]` / `# SPDX-License-Identifier: MIT`.
- 값(시크릿) 자체를 다루지 않는 엔드포인트(프로젝트·디렉토리·대기열 관리)는 잠금 상태에서도 동작해야 한다 — 프로젝트명·경로 문자열은 비밀이 아니다(기존 `list_entries()`가 잠금 상태에서도 동작하는 것과 같은 원칙).
- `/sdk/env`만 실제 복호화된 값을 반환하므로 `VaultLocked`(401)를 강제한다.
- 에러는 항상 `HTTPException(status_code, detail=<사람이 읽을 수 있는 한국어 문자열>)`로 — 기존 `main.py` 관례(예: `raise HTTPException(status_code=401, detail="...") from None`) 그대로 따른다.
- 테스트는 기존 3계층 파일 관례를 그대로 따른다 — repo 레벨(`test_vault.py` 참고), 세션 레벨(`test_vault_session.py` 참고), API 레벨(`test_vault_api.py` 참고, 라우트 함수 직접 호출).
- SYNC-0(번들 내보내기/가져오기)는 이 플랜 범위 밖 — 프로젝트-디렉토리 허용목록은 기기 단위 신뢰 결정이라 번들에 담지 않는다(다른 기기로 이식하면 안 됨).

> **읽는 법(전체 브랜치 리뷰 반영, 사후 기재):** 각 태스크의 예상 테스트 개수(9/15/9/9 등)는 이후 리뷰 라운드에서 테스트가 추가되며 실제로는 더 늘어났다 — 최소 하한으로 읽을 것.

---

### Task 1: `sdk_repo.py` — 프로젝트 디렉토리 + 승인 대기열 CRUD

**Files:**
- Modify: `backend/app/vault_repo.py` (`_SCHEMA` 상수에 테이블 2개 추가, `EVENT_LABELS`에 항목 1개 추가)
- Create: `backend/app/sdk_repo.py`
- Test: `backend/tests/test_sdk_repo.py` (신규 — 이 태스크 범위만)

**Interfaces:**
- Consumes: `vault_repo.connect(path)`(기존), `vault_repo.init_vault(conn, password)`(기존), `vault_repo.unlock(conn, password)`(기존), `vault_repo.add_entry(conn, key, *, service, kind, official_name, value, label=None, project=None, memo=None, expires_at=None) -> int`(기존)
- Produces (Task 2/3/5가 그대로 씀):
  - `sdk_repo.add_project_dir(conn, project: str, path: str, source: str) -> int`
  - `sdk_repo.remove_project_dir(conn, project: str, dir_id: int) -> bool`
  - `sdk_repo.list_project_dirs(conn, project: str) -> list[dict]` (`{id, path, source, created_at}`)
  - `sdk_repo.is_path_approved(conn, project: str, path: str) -> bool`
  - `sdk_repo.add_pending_request(conn, project: str, path: str) -> int`
  - `sdk_repo.list_pending_requests(conn) -> list[dict]` (`{id, project, path, requested_at}`)
  - `sdk_repo.get_pending(conn, pending_id: int) -> dict | None`
  - `sdk_repo.approve_pending(conn, pending_id: int) -> bool`
  - `sdk_repo.deny_pending(conn, pending_id: int) -> bool`
  - `sdk_repo.list_sdk_projects(conn) -> list[dict]` (`{project, key_count}`)
  - `vault_repo.EVENT_LABELS["sdk_fetch"] == "SDK 조회"` (Task 3이 감사 로그에 씀)

- [ ] **Step 1: `vault_repo._SCHEMA`에 새 테이블 2개 추가**

`backend/app/vault_repo.py`의 `_SCHEMA` 상수 끝(`access_log` 테이블 정의 뒤, 닫는 `"""` 앞)에 아래 두 `CREATE TABLE`을 추가한다:

```python
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    kdf_salt       BLOB NOT NULL,
    kdf_time       INTEGER NOT NULL,
    kdf_memory     INTEGER NOT NULL,
    kdf_lanes      INTEGER NOT NULL,
    verifier_nonce BLOB NOT NULL,
    verifier_ct    BLOB NOT NULL,
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    service        TEXT,
    kind           TEXT,
    official_name  TEXT,
    label          TEXT,
    project        TEXT,
    memo           TEXT,
    nonce          BLOB NOT NULL,
    ciphertext     BLOB NOT NULL,
    created_at     TEXT NOT NULL,
    expires_at     TEXT
);
CREATE TABLE IF NOT EXISTS access_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER,
    event    TEXT NOT NULL,
    at       TEXT NOT NULL,
    FOREIGN KEY (entry_id) REFERENCES entries(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS sdk_project_dirs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project    TEXT NOT NULL,
    path       TEXT NOT NULL,
    source     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project, path)
);
CREATE TABLE IF NOT EXISTS sdk_pending_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project      TEXT NOT NULL,
    path         TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    UNIQUE(project, path)
);
"""
```

그리고 `EVENT_LABELS` 딕셔너리(같은 파일)에 한 줄 추가:

```python
EVENT_LABELS = {
    "register": "등록",
    "reveal": "열람",
    "copy": "복사",
    "export": ".env 내보내기",
    "rotate": "키 교체",
    "verify": "유효성 검증",
    "sdk_fetch": "SDK 조회",
}
```

> **사후 정정(전체 브랜치 리뷰):** 위 스키마·CRUD 샘플은 `path` 원본 문자열에 직접 매칭한다(`UNIQUE(project, path)`, `WHERE path = ?`). **구현 중 리뷰로 발견**: 경로를 정규화해서 저장하면 사용자가 보는 표시값이 훼손된다(구분자·대소문자·트레일링 슬래시 차이를 그대로 남겨야 사용자가 등록한 원본을 재확인할 수 있다) — 실제 구현은 `path`(원본, 표시용) / `path_norm`(정규화된 매칭 키) 두 컬럼으로 분리했다(`sdk_repo._normalize_path`, `UNIQUE(project, path_norm)`). 새 스키마를 참고하는 후속 작업은 이 분리를 따라야 한다.
>
> **마이그레이션 경로도 필요하다**: 이 브랜치 히스토리상 이미 예전 스키마(테이블 자체가 없거나, `path_norm` 없는 5컬럼 버전)로 초기화된 vault.db가 있을 수 있다. 테이블 레벨(`CREATE TABLE IF NOT EXISTS`를 `connect()`가 이미 초기화된 금고에도 매번 재실행)과 컬럼 레벨(`ALTER TABLE ADD COLUMN` + 기존 행 백필, `IF NOT EXISTS`로는 기존 테이블에 없는 컬럼을 추가할 수 없으므로) 두 단계 마이그레이션이 모두 필요하다. 실제 구현은 `vault_repo.connect()`가 둘 다 수행한다(`_ensure_path_norm_column` 호출 참고).

- [ ] **Step 2: `backend/app/sdk_repo.py` 생성**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 SDK 접근 관리 — 프로젝트별 허용 디렉토리 + 승인 대기열.

`keylens-env` SDK가 어떤 디렉토리에서 어떤 프로젝트의 키를 가져갈 수 있는지 관리한다.
테이블은 `vault_repo._SCHEMA`에 함께 정의된다(같은 vault.db, 같은 초기화 시점).
여기서 저장하는 건 프로젝트명·경로 문자열뿐 — 시크릿 값은 전혀 다루지 않는다.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_project_dir(conn: sqlite3.Connection, project: str, path: str, source: str) -> int:
    """프로젝트에 허용 디렉토리 등록. source: 'manual'(사전 등록) | 'approved'(승인 프롬프트).

    이미 등록된 (project, path) 조합이면 새로 만들지 않고 기존 id를 반환한다(idempotent).
    """
    row = conn.execute(
        "SELECT id FROM sdk_project_dirs WHERE project = ? AND path = ?", (project, path)
    ).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO sdk_project_dirs (project, path, source, created_at) VALUES (?,?,?,?)",
        (project, path, source, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def remove_project_dir(conn: sqlite3.Connection, project: str, dir_id: int) -> bool:
    """등록 해제. project가 일치하는 행만 지운다(다른 프로젝트 id 오삭제 방지)."""
    cur = conn.execute(
        "DELETE FROM sdk_project_dirs WHERE id = ? AND project = ?", (dir_id, project)
    )
    conn.commit()
    return cur.rowcount > 0


def list_project_dirs(conn: sqlite3.Connection, project: str) -> list[dict]:
    """프로젝트의 허용 디렉토리 목록(등록 순)."""
    rows = conn.execute(
        "SELECT id, path, source, created_at FROM sdk_project_dirs"
        " WHERE project = ? ORDER BY id",
        (project,),
    ).fetchall()
    return [dict(r) for r in rows]


def is_path_approved(conn: sqlite3.Connection, project: str, path: str) -> bool:
    """path가 project에 등록돼 있는지."""
    row = conn.execute(
        "SELECT 1 FROM sdk_project_dirs WHERE project = ? AND path = ?", (project, path)
    ).fetchone()
    return row is not None


def add_pending_request(conn: sqlite3.Connection, project: str, path: str) -> int:
    """미등록 경로의 최초 요청을 대기열에 등록. 이미 대기 중이면 새로 만들지 않는다(idempotent)."""
    row = conn.execute(
        "SELECT id FROM sdk_pending_requests WHERE project = ? AND path = ?", (project, path)
    ).fetchone()
    if row is not None:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO sdk_pending_requests (project, path, requested_at) VALUES (?,?,?)",
        (project, path, _now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_pending_requests(conn: sqlite3.Connection) -> list[dict]:
    """대기 중인 모든 승인 요청(오래된 순)."""
    rows = conn.execute(
        "SELECT id, project, path, requested_at FROM sdk_pending_requests ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_pending(conn: sqlite3.Connection, pending_id: int) -> dict | None:
    """대기 요청 단건 조회. 없으면 None."""
    row = conn.execute(
        "SELECT id, project, path, requested_at FROM sdk_pending_requests WHERE id = ?",
        (pending_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def approve_pending(conn: sqlite3.Connection, pending_id: int) -> bool:
    """대기 요청을 허용 목록(source='approved')으로 옮기고 대기열에서 제거."""
    pending = get_pending(conn, pending_id)
    if pending is None:
        return False
    add_project_dir(conn, pending["project"], pending["path"], source="approved")
    conn.execute("DELETE FROM sdk_pending_requests WHERE id = ?", (pending_id,))
    conn.commit()
    return True


def deny_pending(conn: sqlite3.Connection, pending_id: int) -> bool:
    """대기 요청을 거부(그냥 삭제 — 허용 목록에 올리지 않는다)."""
    cur = conn.execute("DELETE FROM sdk_pending_requests WHERE id = ?", (pending_id,))
    conn.commit()
    return cur.rowcount > 0


def list_sdk_projects(conn: sqlite3.Connection) -> list[dict]:
    """프로젝트가 지정된 금고 항목을 프로젝트별로 묶어 목록화: [{project, key_count}]."""
    rows = conn.execute(
        "SELECT project, COUNT(*) AS key_count FROM entries"
        " WHERE project IS NOT NULL AND project != '' GROUP BY project ORDER BY project"
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 3: 실패하는 테스트 작성 — `backend/tests/test_sdk_repo.py`**

```python
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
```

- [ ] **Step 4: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_repo.py -v`
Expected: `ModuleNotFoundError: No module named 'app.sdk_repo'` 또는 `sqlite3.OperationalError: no such table: sdk_project_dirs` (Step 1/2를 아직 안 했다면). 이미 Step 1~2를 했다면 이 단계는 건너뛰고 바로 Step 5로.

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_repo.py -v`
Expected: `9 passed`

- [ ] **Step 6: 커밋**

```bash
git add backend/app/vault_repo.py backend/app/sdk_repo.py backend/tests/test_sdk_repo.py
git commit -m "feat(backend): RUNTIME-1 프로젝트 디렉토리·승인 대기열 저장소(sdk_repo.py)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: env 값 병합 — `entries_for_env` + `entry_ids_for_names`

**Files:**
- Modify: `backend/app/sdk_repo.py`
- Test: `backend/tests/test_sdk_repo.py` (Task 1 파일에 이어서 추가)

**Interfaces:**
- Consumes: `crypto.decrypt(key, nonce, ciphertext, aad) -> str`(기존, `backend/app/crypto.py`), `vault_repo.add_entry(...)`(Task 1과 동일)
- Produces (Task 3이 그대로 씀):
  - `sdk_repo.entries_for_env(conn, key: bytes, project: str) -> dict[str, str]` — env 변수명 → 복호화된 값. project 전용 키가 이름 충돌 시 전역 키를 덮어씀. `official_name`이 없는 항목은 제외.
  - `sdk_repo.entry_ids_for_names(conn, project: str, names: list[str]) -> dict[str, int]` — env 변수명 → 그 값을 실제로 담고 있던 entry id(감사 로그 기록용, project 전용 우선).

- [ ] **Step 1: 실패하는 테스트를 `test_sdk_repo.py` 끝에 추가**

```python
def test_entries_for_env_merges_global_and_project(conn):
    key = vault_repo.unlock(conn, MASTER)
    vault_repo.add_entry(
        conn, key, service="github", kind="api_key", official_name="GITHUB_TOKEN",
        value="ghp_global", project=None,
    )
    vault_repo.add_entry(
        conn, key, service="notion", kind="api_key", official_name="NOTION_API_KEY",
        value="secret_blog", project="블로그",
    )
    env = sdk_repo.entries_for_env(conn, key, "블로그")
    assert env == {"GITHUB_TOKEN": "ghp_global", "NOTION_API_KEY": "secret_blog"}


def test_entries_for_env_project_overrides_global_on_name_conflict(conn):
    key = vault_repo.unlock(conn, MASTER)
    vault_repo.add_entry(
        conn, key, service="openai", kind="api_key", official_name="OPENAI_API_KEY",
        value="sk-global", project=None,
    )
    vault_repo.add_entry(
        conn, key, service="openai", kind="api_key", official_name="OPENAI_API_KEY",
        value="sk-project-specific", project="블로그",
    )
    env = sdk_repo.entries_for_env(conn, key, "블로그")
    assert env["OPENAI_API_KEY"] == "sk-project-specific"


def test_entries_for_env_other_project_not_included(conn):
    key = vault_repo.unlock(conn, MASTER)
    vault_repo.add_entry(
        conn, key, service="notion", kind="api_key", official_name="NOTION_API_KEY",
        value="secret_other", project="다른프로젝트",
    )
    env = sdk_repo.entries_for_env(conn, key, "블로그")
    assert "NOTION_API_KEY" not in env


def test_entries_for_env_skips_entries_without_official_name(conn):
    key = vault_repo.unlock(conn, MASTER)
    vault_repo.add_entry(
        conn, key, service=None, kind=None, official_name=None,
        value="unknown-value", project="블로그",
    )
    env = sdk_repo.entries_for_env(conn, key, "블로그")
    assert env == {}


def test_entry_ids_for_names_prefers_project_specific_row(conn):
    key = vault_repo.unlock(conn, MASTER)
    global_id = vault_repo.add_entry(
        conn, key, service="openai", kind="api_key", official_name="OPENAI_API_KEY",
        value="sk-global", project=None,
    )
    project_id = vault_repo.add_entry(
        conn, key, service="openai", kind="api_key", official_name="OPENAI_API_KEY",
        value="sk-project", project="블로그",
    )
    ids = sdk_repo.entry_ids_for_names(conn, "블로그", ["OPENAI_API_KEY"])
    assert ids["OPENAI_API_KEY"] == project_id
    assert ids["OPENAI_API_KEY"] != global_id


def test_entry_ids_for_names_empty_list_returns_empty_dict(conn):
    assert sdk_repo.entry_ids_for_names(conn, "블로그", []) == {}
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_repo.py -v -k "entries_for_env or entry_ids_for_names"`
Expected: `AttributeError: module 'app.sdk_repo' has no attribute 'entries_for_env'`

- [ ] **Step 3: `sdk_repo.py` 끝에 구현 추가**

```python
def entries_for_env(conn: sqlite3.Connection, key: bytes, project: str) -> dict[str, str]:
    """project 전용 키 + 전역(project 미지정) 키를 복호화해 official_name→값으로 병합.

    이름이 겹치면 project 전용 키가 우선(override), 겹치지 않으면 합집합.
    official_name이 없는 항목(unknown 등)은 환경변수로 쓸 수 없으니 제외한다.
    """
    from . import crypto

    rows = conn.execute(
        "SELECT official_name, nonce, ciphertext FROM entries"
        " WHERE project IS NULL OR project = '' OR project = ?"
        " ORDER BY CASE WHEN project = ? THEN 1 ELSE 0 END",
        (project, project),
    ).fetchall()
    result: dict[str, str] = {}
    for r in rows:
        name = r["official_name"]
        if not name:
            continue
        aad = name.encode("utf-8")
        result[name] = crypto.decrypt(key, r["nonce"], r["ciphertext"], aad)
    return result


def entry_ids_for_names(conn: sqlite3.Connection, project: str, names: list[str]) -> dict[str, int]:
    """official_name → entry id. entries_for_env와 같은 우선순위(project 전용이 이김) —
    감사 로그에 "실제로 값을 내려준 항목"을 정확히 기록하기 위함."""
    if not names:
        return {}
    placeholders = ",".join("?" for _ in names)
    rows = conn.execute(
        f"SELECT id, official_name, project FROM entries WHERE official_name IN ({placeholders})",
        names,
    ).fetchall()
    result: dict[str, int] = {}
    for r in rows:
        name = r["official_name"]
        if name not in result or r["project"] == project:
            result[name] = int(r["id"])
    return result
```

> **사후 정정(전체 브랜치 리뷰):** 이 함수 초안은 프로젝트 필터가 빠져 있어 실제 구현에서 리뷰로 발견·수정됨 — 아래는 수정된 버전. 원본 초안은 `WHERE official_name IN (...)`에 project 필터가 전혀 없어, 다른 프로젝트의 동일 이름 항목 id를 잘못 골라 감사 로그에 남길 수 있는 실제 버그였다(전역/이 프로젝트가 아닌 제3의 프로젝트 항목까지 후보에 들어가 `r["project"] == project` 비교 순서에 따라 오귀속 가능).
>
> ```python
> def entry_ids_for_names(conn: sqlite3.Connection, project: str, names: list[str]) -> dict[str, int]:
>     """official_name → entry id. entries_for_env와 같은 우선순위(project 전용이 이김,
>     전역·project만 후보 — 다른 프로젝트의 동일 이름 항목은 후보에서 아예 제외) —
>     감사 로그에 "실제로 값을 내려준 항목"을 정확히 기록하기 위함."""
>     if not names:
>         return {}
>     placeholders = ",".join("?" for _ in names)
>     rows = conn.execute(
>         f"SELECT id, official_name FROM entries"
>         f" WHERE official_name IN ({placeholders})"
>         f" AND (project IS NULL OR project = '' OR project = ?)"
>         f" ORDER BY CASE WHEN project = ? THEN 1 ELSE 0 END, id",
>         [*names, project, project],
>     ).fetchall()
>     return {r["official_name"]: int(r["id"]) for r in rows}
> ```

- [ ] **Step 4: 테스트 실행 → 전체 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_repo.py -v`
Expected: `15 passed`

- [ ] **Step 5: 커밋**

```bash
git add backend/app/sdk_repo.py backend/tests/test_sdk_repo.py
git commit -m "feat(backend): RUNTIME-1 env 값 병합(entries_for_env) — 프로젝트 키가 전역 키 override

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `VaultService` 통합 — `sdk_env` + 승인 관리 + 감사 로그

**Files:**
- Modify: `backend/app/vault_session.py`
- Test: `backend/tests/test_sdk_session.py` (신규)

**Interfaces:**
- Consumes: `sdk_repo.is_path_approved`, `sdk_repo.add_pending_request`, `sdk_repo.entries_for_env`, `sdk_repo.entry_ids_for_names`, `sdk_repo.add_project_dir`, `sdk_repo.remove_project_dir`, `sdk_repo.list_project_dirs`, `sdk_repo.list_pending_requests`, `sdk_repo.approve_pending`, `sdk_repo.deny_pending`, `sdk_repo.list_sdk_projects` (전부 Task 1/2), `vault_repo.log_access(conn, entry_id, event)`(기존), `VaultService._require_key()`/`_conn()`(기존, 이 클래스 안)
- Produces (Task 5가 그대로 씀):
  - `class SdkApprovalPending(Exception)` — `vault_session` 모듈에 정의
  - `VaultService.sdk_env(self, project: str, path: str) -> dict[str, str]` — 잠금 시 `VaultLocked`, 미승인 시 `SdkApprovalPending`
  - `VaultService.add_project_dir(self, project: str, path: str) -> dict` (`{id, path, source}`)
  - `VaultService.remove_project_dir(self, project: str, dir_id: int) -> bool`
  - `VaultService.list_projects(self) -> list[dict]`
  - `VaultService.list_project_dirs(self, project: str) -> list[dict]`
  - `VaultService.list_pending(self) -> list[dict]`
  - `VaultService.approve_pending(self, pending_id: int) -> bool`
  - `VaultService.deny_pending(self, pending_id: int) -> bool`

- [ ] **Step 1: 실패하는 테스트 작성 — `backend/tests/test_sdk_session.py`**

```python
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
```

> **사후 정정(전체 브랜치 리뷰):** 원본 샘플은 `vault.add_entry(official_name=..., value=..., project=...)`처럼 `service`/`kind`를 생략했는데, `VaultService.add_entry`는 이 둘을 키워드 전용 필수 인자로 요구해(기본값 없음) 그대로 실행하면 `TypeError`가 난다. 위 샘플은 `service=None, kind=None,`을 넣어 수정된 버전이다.

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_session.py -v`
Expected: `ImportError: cannot import name 'SdkApprovalPending' from 'app.vault_session'`

- [ ] **Step 3: `backend/app/vault_session.py` 수정**

파일 상단 import 줄을 바꾼다:

```python
from . import crypto, sdk_repo, vault_repo
```

`VaultRateLimited` 클래스 정의 바로 뒤(`class VaultService:` 앞)에 새 예외를 추가한다:

```python
class SdkApprovalPending(Exception):
    """미승인 디렉토리 — 요청이 대기열에 등록되고 승인 대기 중(RUNTIME-1)."""
```

파일 맨 끝(`change_password` 메서드 뒤, 클래스 안)에 아래 메서드들을 추가한다(들여쓰기 4칸, 클래스 멤버로):

```python
    # ── RUNTIME-1: SDK 접근 관리 ──
    def sdk_env(self, project: str, path: str) -> dict[str, str]:
        """keylens-env SDK 진입점. path가 project에 대해 승인되지 않았으면 대기열에 등록하고
        SdkApprovalPending을 던진다. 승인됐으면 값을 복호화해 반환하고, 반환한 각 키를
        감사 이력에 'sdk_fetch'로 남긴다. 잠금 상태면 VaultLocked(값은 절대 안 나감).
        """
        key = self._require_key()
        conn = self._conn()
        try:
            if not sdk_repo.is_path_approved(conn, project, path):
                sdk_repo.add_pending_request(conn, project, path)
                raise SdkApprovalPending(
                    f"'{path}'가 '{project}' 프로젝트 키를 요청했어요 — KeyLens에서 허용해 주세요"
                )
            env = sdk_repo.entries_for_env(conn, key, project)
            ids = sdk_repo.entry_ids_for_names(conn, project, list(env.keys()))
            for entry_id in ids.values():
                vault_repo.log_access(conn, entry_id, "sdk_fetch")
            return env
        finally:
            conn.close()

    def add_project_dir(self, project: str, path: str) -> dict:
        """설정 화면에서 디렉토리 사전 등록(source='manual'). 값을 다루지 않아 잠금 상태에서도 가능."""
        conn = self._conn()
        try:
            dir_id = sdk_repo.add_project_dir(conn, project, path, source="manual")
            return {"id": dir_id, "path": path, "source": "manual"}
        finally:
            conn.close()

    def remove_project_dir(self, project: str, dir_id: int) -> bool:
        conn = self._conn()
        try:
            return sdk_repo.remove_project_dir(conn, project, dir_id)
        finally:
            conn.close()

    def list_projects(self) -> list[dict]:
        conn = self._conn()
        try:
            return sdk_repo.list_sdk_projects(conn)
        finally:
            conn.close()

    def list_project_dirs(self, project: str) -> list[dict]:
        conn = self._conn()
        try:
            return sdk_repo.list_project_dirs(conn, project)
        finally:
            conn.close()

    def list_pending(self) -> list[dict]:
        conn = self._conn()
        try:
            return sdk_repo.list_pending_requests(conn)
        finally:
            conn.close()

    def approve_pending(self, pending_id: int) -> bool:
        conn = self._conn()
        try:
            return sdk_repo.approve_pending(conn, pending_id)
        finally:
            conn.close()

    def deny_pending(self, pending_id: int) -> bool:
        conn = self._conn()
        try:
            return sdk_repo.deny_pending(conn, pending_id)
        finally:
            conn.close()
```

- [ ] **Step 4: 테스트 실행 → 전체 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_session.py -v`
Expected: `9 passed`

- [ ] **Step 5: 회귀 확인 — 기존 테스트도 전부 통과하는지**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: 기존 153개 + 이 플랜에서 추가한 테스트(Task 1: 9, Task 2: 6, Task 3: 9) 전부 통과, 실패 0.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/vault_session.py backend/tests/test_sdk_session.py
git commit -m "feat(backend): RUNTIME-1 VaultService.sdk_env — 승인 게이트 + 감사 로그 연동

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Pydantic 모델

**Files:**
- Modify: `backend/app/models.py`

**Interfaces:**
- Consumes: 없음(순수 스키마 정의)
- Produces (Task 5가 그대로 씀):
  - `SdkEnvRequest(project: str, path: str)`
  - `SdkEnvResponse(values: dict[str, str])`
  - `SdkProject(project: str, key_count: int)`
  - `SdkProjectDir(id: int, path: str, source: Literal["manual", "approved"], created_at: str)`
  - `SdkAddDirRequest(path: str)`
  - `SdkPendingRequest(id: int, project: str, path: str, requested_at: str)`

- [ ] **Step 1: `backend/app/models.py` 파일 끝에 추가**

(파일은 이미 `from pydantic import BaseModel, Field`와 `from typing import Literal, Optional`을 상단에 import하고 있다 — 추가 import 불필요.)

```python
# ── RUNTIME-1: SDK 접근 관리 ──


class SdkEnvRequest(BaseModel):
    """keylens-env SDK가 값을 요청할 때 보내는 요청 — 프로젝트명 + 호출 디렉토리 경로."""

    project: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=4096)


class SdkEnvResponse(BaseModel):
    """env 변수명 → 값. 승인된 디렉토리에서만 채워진다(값 있음 — 응답 로깅 금지)."""

    values: dict[str, str]


class SdkProject(BaseModel):
    project: str
    key_count: int


class SdkProjectDir(BaseModel):
    id: int
    path: str
    source: Literal["manual", "approved"]
    created_at: str


class SdkAddDirRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class SdkPendingRequest(BaseModel):
    id: int
    project: str
    path: str
    requested_at: str
```

- [ ] **Step 2: 임포트 확인**

Run: `cd backend && .venv/Scripts/python.exe -c "from app.models import SdkEnvRequest, SdkEnvResponse, SdkProject, SdkProjectDir, SdkAddDirRequest, SdkPendingRequest; print('OK')"`
Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add backend/app/models.py
git commit -m "feat(backend): RUNTIME-1 SDK 요청/응답 Pydantic 모델 추가

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: FastAPI 라우트 (`/sdk/*`) + API 레벨 테스트

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_sdk_api.py` (신규)

**Interfaces:**
- Consumes: `VaultService.sdk_env/add_project_dir/remove_project_dir/list_projects/list_project_dirs/list_pending/approve_pending/deny_pending`(Task 3), `SdkApprovalPending`(Task 3), `SdkEnvRequest/SdkEnvResponse/SdkProject/SdkProjectDir/SdkAddDirRequest/SdkPendingRequest`(Task 4)
- Produces: `POST /sdk/env`, `GET /sdk/projects`, `GET /sdk/projects/{project}/directories`, `POST /sdk/projects/{project}/directories`, `DELETE /sdk/projects/{project}/directories/{dir_id}`, `GET /sdk/pending`, `POST /sdk/pending/{pending_id}/approve`, `POST /sdk/pending/{pending_id}/deny` — Phase 2(프론트 설정 화면)·Phase 3(`keylens-env` 패키지)가 그대로 씀.

- [ ] **Step 1: 실패하는 테스트 작성 — `backend/tests/test_sdk_api.py`**

```python
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_api.py -v`
Expected: `AttributeError: module 'app.main' has no attribute 'sdk_env'`

- [ ] **Step 3: `backend/app/main.py` 수정**

`from .models import (...)` 블록에 새 모델들을 추가한다(알파벳 순서 유지):

```python
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
    SdkAddDirRequest,
    SdkEnvRequest,
    SdkEnvResponse,
    SdkPendingRequest,
    SdkProject,
    SdkProjectDir,
    VaultChangePassword,
    VaultEntryCreate,
    VaultEntryMeta,
    VaultEntryUpdate,
    VaultHistoryEntry,
    VaultImportRequest,
    VaultImportResult,
    VaultInit,
    VaultPassword,
    VaultRotate,
    VaultStatus,
    VaultValue,
    VaultVerifyResult,
)
```

`from .vault_session import VaultLocked, VaultRateLimited, VaultService` 줄을 아래로 바꾼다:

```python
from .vault_session import SdkApprovalPending, VaultLocked, VaultRateLimited, VaultService
```

파일 끝, `vault_change_password` 함수 뒤 · `DEFAULT_PORT` 상수 앞에 새 섹션을 추가한다:

```python
# ── RUNTIME-1: SDK 접근 관리 ──
# keylens-env SDK가 프로젝트별로 어떤 디렉토리에서 값을 가져갈 수 있는지 관리한다.
# /sdk/env 는 실제 값을 반환하므로 인증(잠금 해제) 필수 — 그 외 관리 엔드포인트는
# 프로젝트명·경로 문자열(비밀 아님)만 다루므로 잠금 상태에서도 접근을 막지 않는다.


@app.post("/sdk/env", response_model=SdkEnvResponse)
def sdk_env(body: SdkEnvRequest) -> SdkEnvResponse:
    try:
        values = VAULT.sdk_env(body.project, body.path)
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    except SdkApprovalPending as e:
        raise HTTPException(status_code=403, detail=str(e)) from None
    return SdkEnvResponse(values=values)


@app.get("/sdk/projects", response_model=list[SdkProject])
def sdk_list_projects() -> list[SdkProject]:
    return [SdkProject(**p) for p in VAULT.list_projects()]


@app.get("/sdk/projects/{project}/directories", response_model=list[SdkProjectDir])
def sdk_list_dirs(project: str) -> list[SdkProjectDir]:
    return [SdkProjectDir(**d) for d in VAULT.list_project_dirs(project)]


@app.post("/sdk/projects/{project}/directories", response_model=SdkProjectDir)
def sdk_add_dir(project: str, body: SdkAddDirRequest) -> SdkProjectDir:
    created = VAULT.add_project_dir(project, body.path)
    dirs = VAULT.list_project_dirs(project)
    return next(SdkProjectDir(**d) for d in dirs if d["id"] == created["id"])


@app.delete("/sdk/projects/{project}/directories/{dir_id}")
def sdk_remove_dir(project: str, dir_id: int) -> dict:
    ok = VAULT.remove_project_dir(project, dir_id)
    if not ok:
        raise HTTPException(status_code=404, detail="디렉토리를 찾을 수 없습니다")
    return {"removed": True}


@app.get("/sdk/pending", response_model=list[SdkPendingRequest])
def sdk_list_pending() -> list[SdkPendingRequest]:
    return [SdkPendingRequest(**p) for p in VAULT.list_pending()]


@app.post("/sdk/pending/{pending_id}/approve")
def sdk_approve_pending(pending_id: int) -> dict:
    ok = VAULT.approve_pending(pending_id)
    if not ok:
        raise HTTPException(status_code=404, detail="대기 중인 요청을 찾을 수 없습니다")
    return {"approved": True}


@app.post("/sdk/pending/{pending_id}/deny")
def sdk_deny_pending(pending_id: int) -> dict:
    ok = VAULT.deny_pending(pending_id)
    if not ok:
        raise HTTPException(status_code=404, detail="대기 중인 요청을 찾을 수 없습니다")
    return {"denied": True}
```

- [ ] **Step 4: 테스트 실행 → 전체 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_api.py -v`
Expected: `9 passed`

- [ ] **Step 5: 전체 회귀 스위트 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: 전체(기존 153 + 이 플랜에서 추가한 33개) 실패 0으로 통과.

- [ ] **Step 6: 커밋**

```bash
git add backend/app/main.py backend/tests/test_sdk_api.py
git commit -m "feat(backend): RUNTIME-1 /sdk/* 엔드포인트 — env 조회·프로젝트·승인 대기열 관리

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review 메모 (계획 작성자 확인용)

- **스펙 커버리지**: BACKLOG RUNTIME-1의 "핵심 설계" 중 이 플랜(1/4)이 다루는 범위 — 프로젝트 그룹 단위 접근범위(Task 2)·기본 키 전역+충돌 시 프로젝트 우선(Task 2)·디렉토리 사전등록+승인 프롬프트(Task 1/3)·감사 로그(Task 3) 전부 태스크로 매핑됨. "실행 전제"(KeyLens 실행+잠금해제)는 Task 3의 `_require_key()` 재사용으로 충족. 알림 채널(plyer/Web Notification)·`.keylens.toml` 탐색·PyPI 패키징은 각각 별도 플랜(4/2/3) 범위.
- **플레이스홀더 스캔**: 없음 — 모든 스텝에 완전한 코드·정확한 명령·기대 출력 포함.
- **타입 일관성**: `sdk_env(project: str, path: str)` 시그니처가 Task 3(VaultService)·Task 5(라우트) 동일. `entries_for_env`/`entry_ids_for_names` 반환 타입이 Task 2에서 정의한 그대로 Task 3에서 쓰임. `source: Literal["manual", "approved"]` 값이 Task 1(`sdk_repo.add_project_dir` 호출부)·Task 4(Pydantic 모델) 동일.
