# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""VAULT-1 SQLite 저장소 — **암호문만 저장한다. 평문 값 컬럼은 존재하지 않는다.** (SPEC 6장)

- `meta`: 금고 단위 KDF 파라미터(솔트·강도) + 비밀번호 검증기(verifier). 키는 저장하지 않는다.
- `entries`: 항목 메타데이터 + nonce + 암호문(GCM 태그 포함). 값 평문 컬럼 없음.

`verifier`는 고정 토큰을 키로 암호화한 것 — 잠금 해제 시 이 값 복호화 성공 여부로 비밀번호를 검증한다
(엔트리를 건드리지 않고도 오답 비밀번호를 즉시 거부). 각 항목은 `official_name`을 AAD로 묶어,
DB에서 라벨을 바꿔치기하면 복호화가 깨지도록 한다.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from . import crypto

# 비밀번호 검증기 평문(비밀 아님). 키로 암호화해 meta 에 저장한다.
_VERIFIER_TOKEN = "keylens-vault-verifier-v1"

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
"""

# 감사 이력 이벤트 코드 → 표시 라벨(누가/언제/무엇을 열람·복사·내보냈는지 — SECURITY_REVIEW 3-4).
EVENT_LABELS = {
    "register": "등록",
    "reveal": "열람",
    "copy": "복사",
    "export": ".env 내보내기",
    "rotate": "키 교체",
    "verify": "유효성 검증",
}

# 값 복호화 없이 노출 가능한 메타데이터 컬럼(평문). 잠금 상태에서도 안전.
_META_COLS = "id, service, kind, official_name, label, project, memo, created_at, expires_at"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _aad(official_name: str | None) -> bytes:
    """항목 암호문을 official_name 에 묶는 부가 인증 데이터(변조 방지)."""
    return (official_name or "").encode("utf-8")


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def is_initialized(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='meta'"
    ).fetchone()
    if row is None:
        return False
    return conn.execute("SELECT 1 FROM meta WHERE id = 1").fetchone() is not None


def _params_from_meta(row: sqlite3.Row) -> crypto.KdfParams:
    return crypto.KdfParams(
        salt=row["kdf_salt"],
        time_cost=row["kdf_time"],
        memory_cost=row["kdf_memory"],
        lanes=row["kdf_lanes"],
    )


def init_vault(conn: sqlite3.Connection, password: str) -> bytes:
    """새 금고 초기화 — 스키마 생성 + KDF 파라미터/검증기 저장. 유도된 키를 메모리로 반환."""
    if is_initialized(conn):
        raise ValueError("이미 초기화된 금고입니다")
    conn.executescript(_SCHEMA)
    params = crypto.new_params()
    key = crypto.derive_key(password, params)
    v_nonce, v_ct = crypto.encrypt(key, _VERIFIER_TOKEN)
    conn.execute(
        "INSERT INTO meta (id, kdf_salt, kdf_time, kdf_memory, kdf_lanes,"
        " verifier_nonce, verifier_ct, created_at) VALUES (1,?,?,?,?,?,?,?)",
        (params.salt, params.time_cost, params.memory_cost, params.lanes,
         v_nonce, v_ct, _now()),
    )
    conn.commit()
    return key


def unlock(conn: sqlite3.Connection, password: str) -> bytes:
    """비밀번호로 금고 열기 — 검증기 복호화로 확인. 틀리면 crypto.DecryptError."""
    row = conn.execute("SELECT * FROM meta WHERE id = 1").fetchone()
    if row is None:
        raise ValueError("초기화되지 않은 금고입니다")
    key = crypto.derive_key(password, _params_from_meta(row))
    # 검증기 복호화 실패 = 오답 비밀번호 → DecryptError 전파.
    crypto.decrypt(key, row["verifier_nonce"], row["verifier_ct"])
    return key


def add_entry(
    conn: sqlite3.Connection,
    key: bytes,
    *,
    service: str | None,
    kind: str | None,
    official_name: str | None,
    value: str,
    label: str | None = None,
    project: str | None = None,
    memo: str | None = None,
    expires_at: str | None = None,
) -> int:
    """값을 암호화해 저장. 반환: 새 항목 id. 평문 value 는 저장되지 않는다(project/memo 는 평문 메타)."""
    nonce, ct = crypto.encrypt(key, value, _aad(official_name))
    cur = conn.execute(
        "INSERT INTO entries (service, kind, official_name, label, project, memo,"
        " nonce, ciphertext, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (service, kind, official_name, label, project, memo, nonce, ct, _now(), expires_at),
    )
    entry_id = int(cur.lastrowid)
    log_access(conn, entry_id, "register")  # 등록 이력
    conn.commit()
    return entry_id


def log_access(conn: sqlite3.Connection, entry_id: int, event: str) -> None:
    """감사 이력 한 줄 기록(값 없음). event 는 EVENT_LABELS 의 코드."""
    conn.execute(
        "INSERT INTO access_log (entry_id, event, at) VALUES (?,?,?)",
        (entry_id, event, _now()),
    )
    conn.commit()


def access_history(conn: sqlite3.Connection, entry_id: int) -> list[dict]:
    """항목의 감사 이력을 최신순으로 반환(값 노출 없음). 표시용 라벨로 변환."""
    rows = conn.execute(
        "SELECT event, at FROM access_log WHERE entry_id = ? ORDER BY id DESC",
        (entry_id,),
    ).fetchall()
    return [
        {"date": r["at"][:16].replace("T", " "), "event": EVENT_LABELS.get(r["event"], r["event"])}
        for r in rows
    ]


def list_entries(conn: sqlite3.Connection) -> list[dict]:
    """항목 메타데이터만 반환(값 복호화 없음 — 잠금 상태에서도 안전)."""
    rows = conn.execute(f"SELECT {_META_COLS} FROM entries ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def update_meta(
    conn: sqlite3.Connection,
    entry_id: int,
    *,
    project: str | None = None,
    memo: str | None = None,
    expires_at: str | None = None,
) -> bool:
    """평문 메타데이터(프로젝트·메모·만료일)만 수정. 값·암호문은 건드리지 않는다."""
    cur = conn.execute(
        "UPDATE entries SET project = ?, memo = ?, expires_at = ? WHERE id = ?",
        (project, memo, expires_at, entry_id),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> bool:
    cur = conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()
    return cur.rowcount > 0


def rotate_value(conn: sqlite3.Connection, key: bytes, entry_id: int, new_value: str) -> bool:
    """항목의 값을 새 값으로 교체(재암호화). 옛 암호문은 새 nonce/암호문으로 덮어써 폐기된다.

    서비스 콘솔에서 키를 재발급했을 때 금고의 값을 최신으로 유지하기 위함(SECURITY_REVIEW 2-3).
    official_name(AAD)은 그대로 유지하고, 교체 이력을 남긴다.
    """
    row = conn.execute(
        "SELECT official_name FROM entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if row is None:
        return False
    nonce, ct = crypto.encrypt(key, new_value, _aad(row["official_name"]))
    conn.execute(
        "UPDATE entries SET nonce = ?, ciphertext = ? WHERE id = ?", (nonce, ct, entry_id)
    )
    log_access(conn, entry_id, "rotate")
    conn.commit()
    return True


def get_value(conn: sqlite3.Connection, key: bytes, entry_id: int) -> str:
    """한 항목의 평문 값을 복호화해 반환. 잘못된 키면 crypto.DecryptError."""
    row = conn.execute(
        "SELECT official_name, nonce, ciphertext FROM entries WHERE id = ?",
        (entry_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"항목 {entry_id} 없음")
    return crypto.decrypt(key, row["nonce"], row["ciphertext"], _aad(row["official_name"]))


def change_password(conn: sqlite3.Connection, old_password: str, new_password: str) -> None:
    """마스터 비밀번호 변경 — 새 솔트/키로 검증기와 모든 항목을 재암호화(원자적)."""
    old_key = unlock(conn, old_password)  # 오답이면 여기서 DecryptError
    new_params = crypto.new_params()
    new_key = crypto.derive_key(new_password, new_params)

    rows = conn.execute(
        "SELECT id, official_name, nonce, ciphertext FROM entries"
    ).fetchall()
    try:
        for r in rows:
            aad = _aad(r["official_name"])
            plaintext = crypto.decrypt(old_key, r["nonce"], r["ciphertext"], aad)
            nonce, ct = crypto.encrypt(new_key, plaintext, aad)
            conn.execute(
                "UPDATE entries SET nonce = ?, ciphertext = ? WHERE id = ?",
                (nonce, ct, r["id"]),
            )
        v_nonce, v_ct = crypto.encrypt(new_key, _VERIFIER_TOKEN)
        conn.execute(
            "UPDATE meta SET kdf_salt=?, kdf_time=?, kdf_memory=?, kdf_lanes=?,"
            " verifier_nonce=?, verifier_ct=? WHERE id = 1",
            (new_params.salt, new_params.time_cost, new_params.memory_cost,
             new_params.lanes, v_nonce, v_ct),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
