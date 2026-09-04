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


# ── 인증 백오프가 초기화를 넘어 살아남던 문제 ──


def _burn_attempts(svc: VaultService, n: int = 8) -> None:
    """비밀번호를 잊은 사람이 실제로 하는 일 - 계속 틀린다."""
    from app import crypto
    from app.vault_session import VaultRateLimited

    svc.lock()
    for i in range(n):
        try:
            svc.unlock(f"wrong-guess-{i}")
        except (crypto.DecryptError, VaultRateLimited):
            pass


def test_forgotten_reset_clears_the_auth_backoff(tmp_path):
    """이 기능을 쓰는 사람은 정의상 여러 번 틀린 뒤에 온다.

    실패 이력이 초기화를 넘어 남으면, 새 비밀번호를 정한 직후 **올바른 값으로도** 거부당한다.
    사라진 금고에 대한 실패 횟수를 새 금고에 물려줄 이유가 없다.
    """
    from app.vault_session import VaultRateLimited

    svc = VaultService(str(tmp_path / "vault.db"))
    svc.init("OldPassword2026!")
    _burn_attempts(svc)
    assert svc._fail_count > 0, "선행 조건 - 실패가 쌓여 있어야 한다"

    svc.reset_forgotten()

    assert svc._fail_count == 0
    assert svc._locked_until == 0.0
    svc.init("BrandNewPass2026!")
    svc.lock()
    svc.unlock("BrandNewPass2026!")  # VaultRateLimited 가 나면 실패
    assert svc._is_unlocked() is True


def test_password_reset_also_clears_the_backoff(tmp_path):
    svc = VaultService(str(tmp_path / "vault.db"))
    svc.init("OldPassword2026!")
    _burn_attempts(svc)

    svc.reset("OldPassword2026!")

    assert svc._fail_count == 0
    assert svc._locked_until == 0.0


def test_lock_does_not_clear_the_backoff(tmp_path):
    """무차별 대입 방어의 핵심 - /vault/lock 은 인증이 없다.

    잠그는 것으로 백오프가 지워지면, 공격자는 추측 사이사이에 잠금을 걸어 지연을 매번
    초기화할 수 있다. 그러면 지수 백오프가 통째로 무력화된다.
    """
    svc = VaultService(str(tmp_path / "vault.db"))
    svc.init("OldPassword2026!")
    _burn_attempts(svc, n=5)
    before = svc._fail_count

    svc.lock()

    assert svc._fail_count == before, "잠그는 것만으로 실패 이력이 사라지면 안 된다"


def test_rate_limit_message_has_no_em_dash():
    """한글 Windows 콘솔(cp949)에서 em dash 는 UnicodeEncodeError 로 죽는다.

    이 메시지는 SDK·CLI 를 거쳐 터미널로 나갈 수 있다.
    """
    from app.vault_session import VaultRateLimited

    msg = str(VaultRateLimited(12.3))

    assert "\u2014" not in msg
    msg.encode("cp949")  # 인코딩 자체가 실패하면 안 된다
