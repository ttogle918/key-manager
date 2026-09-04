# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 SDK 접근 관리 — 프로젝트별 허용 디렉토리 + 승인 대기열.

`keylens-env` SDK가 어떤 디렉토리에서 어떤 프로젝트의 키를 가져갈 수 있는지 관리한다.
테이블은 `vault_repo._SCHEMA`에 함께 정의된다(같은 vault.db, 같은 초기화 시점).
여기서 저장하는 건 프로젝트명·경로 문자열뿐 — 시크릿 값은 전혀 다루지 않는다.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_path(path: str) -> str:
    """허용 목록 비교용 경로 정규화 — 구분자·대소문자·트레일링 슬래시 차이를 흡수한다.

    `os.path.abspath` 대신 `os.path.normpath`를 쓴다: 이 모듈이 다루는 경로는
    실제 파일시스템 경로가 아닐 수 있어(테스트의 `/repo/blog` 등) abspath 는
    테스트 실행 cwd 기준으로 잘못 해석될 수 있다. normpath+normcase 는
    상대성은 건드리지 않고 표기 차이만 정규화한다.

    주의: `os.path.normcase`는 POSIX에서는 아무 것도 하지 않는 no-op이다(대소문자
    구분 파일시스템 전제) — 대소문자 폴딩은 실질적으로 Windows에서만 일어난다.
    """
    return os.path.normcase(os.path.normpath(path))


def add_project_dir(conn: sqlite3.Connection, project: str, path: str, source: str) -> int:
    """프로젝트에 허용 디렉토리 등록. source: 'manual'(사전 등록) | 'approved'(승인 프롬프트).

    이미 등록된 (project, path) 조합이면 새로 만들지 않고 기존 id를 반환한다(idempotent).

    `path`는 호출자가 넘긴 원본 문자열 그대로 저장한다(표시용) — 정규화된 값은
    `path_norm` 컬럼에 별도로 저장해 매칭·중복 판정에만 쓴다.
    """
    norm = _normalize_path(path)
    # SELECT 후 INSERT 로 나누면 두 요청이 동시에 들어올 때 둘 다 "없음"을 보고 INSERT 해
    # UNIQUE 제약에 걸린다(IntegrityError -> 500). ON CONFLICT DO NOTHING 으로 한 문장에서
    # 처리하고, 충돌로 아무 행도 안 들어갔으면 기존 행 id를 읽어 돌려준다.
    conn.execute(
        "INSERT INTO sdk_project_dirs (project, path, path_norm, source, created_at)"
        " VALUES (?,?,?,?,?) ON CONFLICT(project, path_norm) DO NOTHING",
        (project, path, norm, source, _now()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM sdk_project_dirs WHERE project = ? AND path_norm = ?", (project, norm)
    ).fetchone()
    return int(row["id"])


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


def list_all_dirs(conn: sqlite3.Connection) -> list[dict]:
    """모든 컬렉션의 허용 디렉토리를 한 번에(컬렉션명 포함, 컬렉션 -> 등록순).

    "내가 뭘 허용해 뒀지"는 컬렉션을 하나씩 열어보며 답할 질문이 아니다. 프론트가 컬렉션
    수만큼 요청을 날리지 않도록 여기서 한 번에 준다.
    """
    rows = conn.execute(
        "SELECT id, project, path, source, created_at FROM sdk_project_dirs"
        " ORDER BY project, id"
    ).fetchall()
    return [dict(r) for r in rows]


def is_path_approved(conn: sqlite3.Connection, project: str, path: str) -> bool:
    """path가 project에 등록돼 있는지."""
    norm = _normalize_path(path)
    row = conn.execute(
        "SELECT 1 FROM sdk_project_dirs WHERE project = ? AND path_norm = ?", (project, norm)
    ).fetchone()
    return row is not None


def is_pending(conn: sqlite3.Connection, project: str, path: str) -> bool:
    """path가 project에 대해 이미 대기열에 올라와 있는지."""
    norm = _normalize_path(path)
    row = conn.execute(
        "SELECT 1 FROM sdk_pending_requests WHERE project = ? AND path_norm = ?",
        (project, norm),
    ).fetchone()
    return row is not None


def add_pending_request(conn: sqlite3.Connection, project: str, path: str) -> int:
    """미등록 경로의 최초 요청을 대기열에 등록. 이미 대기 중이면 새로 만들지 않는다(idempotent).

    `path`는 원본 문자열 그대로 저장하고, 매칭은 `path_norm`으로 한다(add_project_dir와 동일 패턴).
    """
    norm = _normalize_path(path)
    # add_project_dir 와 같은 이유로 한 문장에서 처리한다 - 여러 프로세스가 같은 디렉토리에서
    # 동시에 load_env() 를 호출하는 건 실제로 일어나는 일이고, 예전 구현은 그때 500을 냈다.
    conn.execute(
        "INSERT INTO sdk_pending_requests (project, path, path_norm, requested_at)"
        " VALUES (?,?,?,?) ON CONFLICT(project, path_norm) DO NOTHING",
        (project, path, norm, _now()),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM sdk_pending_requests WHERE project = ? AND path_norm = ?",
        (project, norm),
    ).fetchone()
    return int(row["id"])


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


def entries_for_env(conn: sqlite3.Connection, key: bytes, project: str) -> dict[str, str]:
    """project 전용 키 + 전역(project 미지정) 키를 복호화해 official_name→값으로 병합.

    이름이 겹치면 project 전용 키가 우선(override), 겹치지 않으면 합집합.
    official_name이 없는 항목(unknown 등)은 환경변수로 쓸 수 없으니 제외한다.

    두 단계로 나눠 처리한다: 먼저 이름별로 "이길" 행 하나만 골라내고(복호화 없음),
    그다음 이긴 행만 복호화한다 — override로 가려지는 전역 항목까지 불필요하게
    평문으로 만들지 않기 위함(메모리에 남는 불필요한 평문 최소화).
    """
    from . import crypto

    rows = conn.execute(
        "SELECT official_name, nonce, ciphertext FROM entries"
        " WHERE project IS NULL OR project = '' OR project = ?"
        " ORDER BY CASE WHEN project = ? THEN 1 ELSE 0 END, id",
        (project, project),
    ).fetchall()
    winners: dict[str, sqlite3.Row] = {}
    for r in rows:
        name = r["official_name"]
        if not name:
            continue
        winners[name] = r  # 순서상 project 전용 행이 나중에 와서 전역 행을 덮어씀
    result: dict[str, str] = {}
    for name, r in winners.items():
        # AAD는 vault_repo._aad(official_name)과 동일한 계산을 의도적으로 중복한다
        # (vault_repo._aad는 비공개라 import 대신 여기서 직접 재현) — 두 곳을 함께 바꿔야 한다.
        aad = name.encode("utf-8")
        result[name] = crypto.decrypt(key, r["nonce"], r["ciphertext"], aad)
    return result


def entry_ids_for_names(conn: sqlite3.Connection, project: str, names: list[str]) -> dict[str, int]:
    """official_name → entry id. entries_for_env와 같은 우선순위(project 전용이 이김,
    전역·project만 후보 — 다른 프로젝트의 동일 이름 항목은 후보에서 아예 제외) —
    감사 로그에 "실제로 값을 내려준 항목"을 정확히 기록하기 위함."""
    if not names:
        return {}
    placeholders = ",".join("?" for _ in names)
    rows = conn.execute(
        "SELECT id, official_name FROM entries"
        f" WHERE official_name IN ({placeholders})"
        " AND (project IS NULL OR project = '' OR project = ?)"
        " ORDER BY CASE WHEN project = ? THEN 1 ELSE 0 END, id",
        [*names, project, project],
    ).fetchall()
    return {r["official_name"]: int(r["id"]) for r in rows}
