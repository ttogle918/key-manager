# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""VAULT-1 암호화 저장소 테스트 (SPEC 6장 AC). 모든 값은 더미."""
import sqlite3

import pytest

from app import crypto, vault_repo

MASTER = "correct horse battery staple"
DUMMY_VALUE = "sk-proj-DummyTwoThreeAbcdEfghTwoThree"  # 명백한 가짜


@pytest.fixture
def db(tmp_path):
    conn = vault_repo.connect(str(tmp_path / "vault.db"))
    yield conn
    conn.close()


# ── crypto 코어 ──
def test_crypto_roundtrip():
    params = crypto.new_params()
    key = crypto.derive_key(MASTER, params)
    nonce, ct = crypto.encrypt(key, DUMMY_VALUE)
    assert crypto.decrypt(key, nonce, ct) == DUMMY_VALUE


def test_crypto_same_password_same_key():
    params = crypto.new_params()
    assert crypto.derive_key(MASTER, params) == crypto.derive_key(MASTER, params)


def test_crypto_wrong_key_rejected():
    params = crypto.new_params()
    key = crypto.derive_key(MASTER, params)
    nonce, ct = crypto.encrypt(key, DUMMY_VALUE)
    wrong = crypto.derive_key("wrong password", params)
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt(wrong, nonce, ct)


def test_crypto_tamper_detected():
    params = crypto.new_params()
    key = crypto.derive_key(MASTER, params)
    nonce, ct = crypto.encrypt(key, DUMMY_VALUE)
    tampered = bytes([ct[0] ^ 0x01]) + ct[1:]  # 1비트 변조 → 태그 불일치
    with pytest.raises(crypto.DecryptError):
        crypto.decrypt(key, nonce, tampered)


# ── vault_repo (AC) ──
def test_save_load_roundtrip(db):
    """🧪 저장→로드 라운드트립으로 원문 복원."""
    key = vault_repo.init_vault(db, MASTER)
    eid = vault_repo.add_entry(
        db, key, service="openai", kind="api_key",
        official_name="OPENAI_API_KEY", value=DUMMY_VALUE,
    )
    assert vault_repo.get_value(db, key, eid) == DUMMY_VALUE


def test_wrong_master_rejected(db):
    """🧪 틀린 마스터 비밀번호 → 복호화 실패(태그 불일치)로 안전하게 거부."""
    vault_repo.init_vault(db, MASTER)
    with pytest.raises(crypto.DecryptError):
        vault_repo.unlock(db, "not the password")


def test_sqlite_has_no_plaintext(db, tmp_path):
    """🧪 SQLite 파일을 직접 열어도 평문 키가 안 보임."""
    key = vault_repo.init_vault(db, MASTER)
    vault_repo.add_entry(
        db, key, service="openai", kind="api_key",
        official_name="OPENAI_API_KEY", value=DUMMY_VALUE,
    )
    db.commit()
    # 별도 커넥션으로 원시 조회 — 어느 컬럼에도 평문 값이 없어야 한다.
    raw = sqlite3.connect(str(tmp_path / "vault.db"))
    try:
        cols = [r[1] for r in raw.execute("PRAGMA table_info(entries)")]
        assert "value" not in cols and "plaintext" not in cols
        rows = raw.execute("SELECT * FROM entries").fetchall()
        blob = repr(rows).encode("utf-8", "ignore")
        assert DUMMY_VALUE.encode() not in blob
    finally:
        raw.close()


def test_list_entries_metadata_only(db):
    key = vault_repo.init_vault(db, MASTER)
    vault_repo.add_entry(
        db, key, service="openai", kind="api_key",
        official_name="OPENAI_API_KEY", value=DUMMY_VALUE, label="API Key",
    )
    items = vault_repo.list_entries(db)
    assert len(items) == 1
    assert items[0]["official_name"] == "OPENAI_API_KEY"
    assert "value" not in items[0] and "ciphertext" not in items[0]


def test_change_password_reencrypts(db):
    """✅ 마스터 비밀번호 변경 후에도 기존 항목 정상 복호화, 옛 비밀번호는 거부."""
    key = vault_repo.init_vault(db, MASTER)
    eid = vault_repo.add_entry(
        db, key, service="openai", kind="api_key",
        official_name="OPENAI_API_KEY", value=DUMMY_VALUE,
    )
    new_master = "a brand new master phrase"
    vault_repo.change_password(db, MASTER, new_master)

    with pytest.raises(crypto.DecryptError):
        vault_repo.unlock(db, MASTER)  # 옛 비밀번호 거부
    new_key = vault_repo.unlock(db, new_master)
    assert vault_repo.get_value(db, new_key, eid) == DUMMY_VALUE


def test_aad_binding_detects_label_swap(db):
    """official_name(AAD) 을 DB 에서 바꿔치기하면 복호화가 깨진다(무결성)."""
    key = vault_repo.init_vault(db, MASTER)
    eid = vault_repo.add_entry(
        db, key, service="openai", kind="api_key",
        official_name="OPENAI_API_KEY", value=DUMMY_VALUE,
    )
    db.execute("UPDATE entries SET official_name = 'KAKAO_ADMIN_KEY' WHERE id = ?", (eid,))
    db.commit()
    with pytest.raises(crypto.DecryptError):
        vault_repo.get_value(db, key, eid)
