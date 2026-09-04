# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""비밀번호를 잊었을 때의 금고 초기화(VAULT-RESET 확장).

기존 /vault/reset 은 마스터 비밀번호를 요구해서, 정작 그걸 잊은 사람은 쓸 수 없었다.
여기서는 인증 대신 확인 문구를 요구한다 - 금고 파일은 디스크에 그대로 있어 기기 접근이
가능하면 어차피 지울 수 있으므로, 인증을 붙여도 막아지는 공격이 없고 대가만 크다.
"""
import pytest
from fastapi import HTTPException

from app import main
from app.models import FORGOTTEN_RESET_PHRASE, VaultEntryCreate, VaultForgottenReset, VaultInit
from app.vault_session import VaultService

MASTER = "correct horse battery staple"


@pytest.fixture
def vault(tmp_path, monkeypatch):
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    monkeypatch.setattr(main, "VAULT", svc)
    main.vault_init(VaultInit(password=MASTER))
    main.vault_add(
        VaultEntryCreate(
            service="notion", kind="api_key", official_name="NOTION_API_KEY",
            value="secret_dummy", project="블로그",
        )
    )
    return svc


def test_forgotten_reset_works_without_the_password(vault):
    """요점 - 비밀번호를 모르는 채로도 초기 상태로 돌아갈 수 있어야 한다."""
    status = main.vault_reset_forgotten(VaultForgottenReset(confirmation=FORGOTTEN_RESET_PHRASE))

    assert status.initialized is False
    assert status.unlocked is False
    # 초기화 뒤에는 새 비밀번호로 다시 만들 수 있어야 한다(이게 이 기능의 목적이다).
    main.vault_init(VaultInit(password="a totally different one!"))
    assert vault.is_initialized() is True


def test_forgotten_reset_wipes_the_entries(vault):
    main.vault_reset_forgotten(VaultForgottenReset(confirmation=FORGOTTEN_RESET_PHRASE))
    main.vault_init(VaultInit(password="a totally different one!"))

    assert main.vault_list() == []


def test_wrong_confirmation_phrase_is_refused(vault):
    """막아야 하는 건 공격자가 아니라 실수다 - 문구가 다르면 아무 일도 일어나면 안 된다."""
    for wrong in ("", "삭제", "모두삭제", "delete all"):
        with pytest.raises(HTTPException) as e:
            main.vault_reset_forgotten(VaultForgottenReset(confirmation=wrong))
        assert e.value.status_code == 422, wrong

    assert vault.is_initialized() is True, "거부됐는데 금고가 사라지면 안 된다"


def test_surrounding_whitespace_is_forgiven(vault):
    """붙여넣다 공백이 섞이는 건 흔하다 - 그걸로 실패시키면 사용자만 답답하다."""
    status = main.vault_reset_forgotten(
        VaultForgottenReset(confirmation=f"  {FORGOTTEN_RESET_PHRASE}  ")
    )

    assert status.initialized is False


def test_forgotten_reset_on_an_empty_vault_returns_409(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "VAULT", VaultService(str(tmp_path / "vault.db")))

    with pytest.raises(HTTPException) as e:
        main.vault_reset_forgotten(VaultForgottenReset(confirmation=FORGOTTEN_RESET_PHRASE))

    assert e.value.status_code == 409


def test_password_based_reset_still_requires_the_password(vault):
    """기존 경로는 그대로 둔다 - 잠금 해제된 세션만으로 삭제되면 안 된다는 판단은 유효하다."""
    from app.models import VaultPassword

    with pytest.raises(HTTPException) as e:
        main.vault_reset(VaultPassword(password="wrong password"))

    assert e.value.status_code == 401
    assert vault.is_initialized() is True
