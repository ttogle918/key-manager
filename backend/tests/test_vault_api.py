# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""VAULT-2 엔드포인트 상태코드 매핑 테스트. httpx(certifi/MPL) 회피 — 라우트 함수 직접 호출."""
import pytest
from fastapi import HTTPException

from app import main
from app.models import VaultChangePassword, VaultEntryCreate, VaultPassword
from app.vault_session import VaultService

MASTER = "correct horse battery staple"
DUMMY = "sk-proj-DummyTwoThreeAbcdEfghTwoThree"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """main.VAULT 를 임시 경로의 새 금고로 교체."""
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    monkeypatch.setattr(main, "VAULT", svc)
    return svc


def test_status_uninitialized(vault):
    st = main.vault_status()
    assert st.initialized is False and st.unlocked is False


def test_init_then_status(vault):
    st = main.vault_init(VaultPassword(password=MASTER))
    assert st.initialized is True and st.unlocked is True


def test_init_twice_conflict(vault):
    main.vault_init(VaultPassword(password=MASTER))
    with pytest.raises(HTTPException) as e:
        main.vault_init(VaultPassword(password=MASTER))
    assert e.value.status_code == 409


def test_unlock_wrong_password_401(vault):
    main.vault_init(VaultPassword(password=MASTER))
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.vault_unlock(VaultPassword(password="nope"))
    assert e.value.status_code == 401


def test_add_and_get_value_flow(vault):
    main.vault_init(VaultPassword(password=MASTER))
    meta = main.vault_add(
        VaultEntryCreate(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=DUMMY)
    )
    assert meta.official_name == "OPENAI_API_KEY"
    got = main.vault_get_value(meta.id)
    assert got.value == DUMMY


def test_add_when_locked_401(vault):
    main.vault_init(VaultPassword(password=MASTER))
    main.vault_lock()
    with pytest.raises(HTTPException) as e:
        main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    assert e.value.status_code == 401


def test_get_value_when_locked_401(vault):
    main.vault_init(VaultPassword(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_lock()
    # 잠금 상태: 목록(메타)은 되지만 값은 401
    assert len(main.vault_list()) == 1
    with pytest.raises(HTTPException) as e:
        main.vault_get_value(meta.id)
    assert e.value.status_code == 401


def test_change_password_wrong_old_401(vault):
    main.vault_init(VaultPassword(password=MASTER))
    with pytest.raises(HTTPException) as e:
        main.vault_change_password(
            VaultChangePassword(old_password="wrong", new_password="new long password")
        )
    assert e.value.status_code == 401
