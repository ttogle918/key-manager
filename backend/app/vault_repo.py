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

import base64
import binascii
import os
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
CREATE TABLE IF NOT EXISTS sdk_project_dirs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project    TEXT NOT NULL,
    path       TEXT NOT NULL,
    path_norm  TEXT NOT NULL,
    source     TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project, path_norm)
);
CREATE TABLE IF NOT EXISTS sdk_pending_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project      TEXT NOT NULL,
    path         TEXT NOT NULL,
    path_norm    TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    UNIQUE(project, path_norm)
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
    "sdk_fetch": "SDK 조회",
}

# 값 복호화 없이 노출 가능한 메타데이터 컬럼(평문). 잠금 상태에서도 안전.
_META_COLS = "id, service, kind, official_name, label, project, memo, created_at, expires_at"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _aad(official_name: str | None) -> bytes:
    """항목 암호문을 official_name 에 묶는 부가 인증 데이터(변조 방지)."""
    return (official_name or "").encode("utf-8")


def _ensure_path_norm_column(conn: sqlite3.Connection, table: str) -> None:
    """구버전 vault.db에 path_norm 컬럼이 없으면 추가하고, 기존 행의 값을 채운다(RUNTIME-1).

    CREATE TABLE IF NOT EXISTS는 테이블이 이미 있으면 컬럼 모양은 손대지 않으므로,
    이 브랜치의 중간 커밋 시점(path_norm 없는 5컬럼 스키마)을 거친 vault.db를 위한
    보강 마이그레이션이다. os.path.normcase(os.path.normpath(...))로 채운다
    (sdk_repo._normalize_path와 동일한 계산이지만, 계층 분리를 위해 여기서 직접 계산한다 —
    vault_repo가 sdk_repo를 import하지 않는다).
    """
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if "path_norm" not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN path_norm TEXT NOT NULL DEFAULT ''")
        rows = conn.execute(f"SELECT id, path FROM {table}").fetchall()
        for r in rows:
            norm = os.path.normcase(os.path.normpath(r["path"]))
            conn.execute(f"UPDATE {table} SET path_norm = ? WHERE id = ?", (norm, r["id"]))
        conn.commit()
    # 이 브랜치의 중간 스키마(5컬럼, path_norm 없음)를 거친 DB는 테이블 레벨
    # UNIQUE(project, path_norm) 제약이 없다 — 인덱스로 동등한 보호를 준다(RUNTIME-1 3차 리뷰).
    conn.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_project_path_norm ON {table}(project, path_norm)"
    )


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # 이미 초기화된 금고(= meta 테이블 존재)라면, 이후 버전에서 _SCHEMA 에 추가된
    # 새 테이블(CREATE TABLE IF NOT EXISTS)을 이 연결 시점에 채워 넣는다 — 마이그레이션.
    # 초기화되지 않은 빈 파일에는 실행하지 않는다: init_vault() 의
    # is_initialized() 판단(= "아직 초기화 안 됨")을 건드리면 안 되기 때문.
    if is_initialized(conn):
        conn.executescript(_SCHEMA)
        # CREATE TABLE IF NOT EXISTS는 테이블이 이미 있으면 컬럼 모양을 바꾸지 않는다 —
        # path_norm 없는 구버전 sdk_project_dirs/sdk_pending_requests(5컬럼)를 위한
        # 컬럼 레벨 보강 마이그레이션(3차 리뷰 반영).
        _ensure_path_norm_column(conn, "sdk_project_dirs")
        _ensure_path_norm_column(conn, "sdk_pending_requests")
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
    """비밀번호로 금고 열기 — 검증기 복호화로 확인. 틀리면 crypto.DecryptError.

    is_initialized()로 먼저 확인한다: meta 테이블 자체가 없는 진짜 미초기화 db(테이블이 아직 한
    번도 생성된 적 없음)와 reset_vault() 이후처럼 테이블은 있으나 행이 비어 있는 경우를 모두
    ValueError로 통일해서 처리하기 위함(둘 다 그냥 SELECT하면 후자만 처리되고 전자는
    sqlite3.OperationalError로 새어나간다).
    """
    if not is_initialized(conn):
        raise ValueError("초기화되지 않은 금고입니다")
    row = conn.execute("SELECT * FROM meta WHERE id = 1").fetchone()
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


# ── SYNC-0: 암호화 금고 내보내기/가져오기 ──
# 번들은 전부 암호문·KDF 파라미터·검증기뿐이다(평문·키 없음). 여는 열쇠는 마스터 비밀번호.
BUNDLE_FORMAT = "keylens-vault"
BUNDLE_VERSION = 1

# 항목 삽입 컬럼(id·AUTOINCREMENT 제외 — 가져올 때 id 재부여).
_ENTRY_INSERT = (
    "INSERT INTO entries (service, kind, official_name, label, project, memo,"
    " nonce, ciphertext, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?,?,?)"
)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def export_bundle(conn: sqlite3.Connection) -> dict:
    """금고 전체를 이식 가능한 암호문 번들(dict)로 직렬화.

    평문 값·유도 키는 절대 포함하지 않는다. 다른 기기의 KeyLens 가 같은 마스터
    비밀번호로 열 수 있도록 KDF 파라미터와 검증기를 함께 담는다(제로 널리지 유지).
    """
    meta = conn.execute("SELECT * FROM meta WHERE id = 1").fetchone()
    if meta is None:
        raise ValueError("초기화되지 않은 금고입니다")
    rows = conn.execute(
        "SELECT service, kind, official_name, label, project, memo,"
        " nonce, ciphertext, created_at, expires_at FROM entries ORDER BY id"
    ).fetchall()
    return {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "exported_at": _now(),
        "kdf": {
            "salt": _b64(meta["kdf_salt"]),
            "time": meta["kdf_time"],
            "memory": meta["kdf_memory"],
            "lanes": meta["kdf_lanes"],
        },
        "verifier": {
            "nonce": _b64(meta["verifier_nonce"]),
            "ct": _b64(meta["verifier_ct"]),
        },
        "entries": [
            {
                "service": r["service"],
                "kind": r["kind"],
                "official_name": r["official_name"],
                "label": r["label"],
                "project": r["project"],
                "memo": r["memo"],
                "nonce": _b64(r["nonce"]),
                "ciphertext": _b64(r["ciphertext"]),
                "created_at": r["created_at"],
                "expires_at": r["expires_at"],
            }
            for r in rows
        ],
    }


def parse_bundle(bundle: dict) -> tuple[crypto.KdfParams, bytes, bytes, list[dict]]:
    """번들을 검증·파싱해 (KDF params, 검증기 nonce, 검증기 ct, 항목 리스트) 반환.

    형식/버전 불일치·손상은 ValueError 로 명확히 실패한다(크래시 금지).
    """
    if not isinstance(bundle, dict):
        raise ValueError("잘못된 금고 파일 형식입니다")
    if bundle.get("format") != BUNDLE_FORMAT:
        raise ValueError("KeyLens 금고 파일이 아닙니다")
    ver = bundle.get("version")
    if ver != BUNDLE_VERSION:
        raise ValueError(
            f"지원하지 않는 금고 파일 버전입니다(파일 v{ver}, 지원 v{BUNDLE_VERSION})"
        )
    try:
        kdf = bundle["kdf"]
        verifier = bundle["verifier"]
        entries = bundle["entries"]
        if not isinstance(entries, list):
            raise ValueError("entries 필드가 손상되었습니다")
        params = crypto.KdfParams(
            salt=base64.b64decode(kdf["salt"]),
            time_cost=int(kdf["time"]),
            memory_cost=int(kdf["memory"]),
            lanes=int(kdf["lanes"]),
        )
        v_nonce = base64.b64decode(verifier["nonce"])
        v_ct = base64.b64decode(verifier["ct"])
    except (KeyError, TypeError, ValueError, binascii.Error) as e:
        raise ValueError("금고 파일이 손상되었습니다") from e
    return params, v_nonce, v_ct, entries


def replace_with_bundle(
    conn: sqlite3.Connection,
    params: crypto.KdfParams,
    v_nonce: bytes,
    v_ct: bytes,
    entries: list[dict],
) -> int:
    """기존 금고를 번들로 통째 교체(원자적). 암호문은 그대로 이식(재암호화 없음)."""
    conn.executescript(_SCHEMA)  # 대상이 빈 기기여도 스키마부터 보장(복원 시나리오)
    try:
        conn.execute("DELETE FROM access_log")
        conn.execute("DELETE FROM entries")
        conn.execute("DELETE FROM meta")
        conn.execute(
            "INSERT INTO meta (id, kdf_salt, kdf_time, kdf_memory, kdf_lanes,"
            " verifier_nonce, verifier_ct, created_at) VALUES (1,?,?,?,?,?,?,?)",
            (params.salt, params.time_cost, params.memory_cost, params.lanes,
             v_nonce, v_ct, _now()),
        )
        n = 0
        for e in entries:
            conn.execute(
                _ENTRY_INSERT,
                (e.get("service"), e.get("kind"), e.get("official_name"), e.get("label"),
                 e.get("project"), e.get("memo"), base64.b64decode(e["nonce"]),
                 base64.b64decode(e["ciphertext"]), e.get("created_at") or _now(),
                 e.get("expires_at")),
            )
            n += 1
        conn.commit()
        return n
    except Exception:
        conn.rollback()
        raise


def merge_bundle(
    conn: sqlite3.Connection,
    existing_key: bytes,
    bundle_key: bytes,
    entries: list[dict],
) -> tuple[int, int]:
    """번들 항목을 기존 금고 키로 재암호화해 병합(원자적). 반환: (가져옴, 건너뜀).

    중복 `official_name` 은 안전하게 건너뛴다(기존 항목 무손상). 번들 항목 하나라도
    복호화에 실패하면(손상) 전체 롤백 — 기존 금고를 절대 훼손하지 않는다.
    """
    existing = {
        r["official_name"]
        for r in conn.execute("SELECT official_name FROM entries").fetchall()
    }
    imported = skipped = 0
    try:
        for e in entries:
            name = e.get("official_name")
            if name in existing:
                skipped += 1
                continue
            plaintext = crypto.decrypt(
                bundle_key, base64.b64decode(e["nonce"]),
                base64.b64decode(e["ciphertext"]), _aad(name),
            )
            nonce, ct = crypto.encrypt(existing_key, plaintext, _aad(name))
            cur = conn.execute(
                _ENTRY_INSERT,
                (e.get("service"), e.get("kind"), name, e.get("label"), e.get("project"),
                 e.get("memo"), nonce, ct, e.get("created_at") or _now(), e.get("expires_at")),
            )
            log_access(conn, int(cur.lastrowid), "register")
            existing.add(name)
            imported += 1
        conn.commit()
        return imported, skipped
    except Exception:
        conn.rollback()
        raise


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


def reset_vault(conn: sqlite3.Connection) -> None:
    """금고를 완전히 비우고 미초기화 상태로 되돌린다(원자적).

    항목·메타(마스터 비밀번호 검증기·KDF 파라미터)·감사이력·SDK 디렉토리 승인 기록(RUNTIME-1)까지
    전부 삭제한다. meta 행이 사라지면 is_initialized()가 자동으로 False가 된다. vault.db 파일 자체는
    남는다(같은 파일에 다시 /vault/init 가능) — 교육·공용 PC에서 다음 사용자에게 이전 사용자의 흔적을
    남기지 않기 위한 용도(VAULT-RESET).
    """
    try:
        conn.execute("DELETE FROM access_log")
        conn.execute("DELETE FROM entries")
        conn.execute("DELETE FROM meta")
        conn.execute("DELETE FROM sdk_project_dirs")
        conn.execute("DELETE FROM sdk_pending_requests")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
