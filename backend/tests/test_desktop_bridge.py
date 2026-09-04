# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""데스크톱 셸 전용 기능(폴더 선택창)의 백엔드 쪽 계약 테스트.

핵심은 "브라우저에서는 없는 기능"이라는 걸 백엔드가 정직하게 말하는 것이다. 프론트가
버튼을 그려 놓고 눌렀을 때 실패하는 것보다, 애초에 안 그리는 쪽이 낫다.
"""
import pytest
from fastapi import HTTPException

from app import desktop, main
from app.models import VaultInit
from app.vault_session import VaultService

MASTER = "correct horse battery staple"


@pytest.fixture(autouse=True)
def no_picker():
    """테스트마다 주입 상태를 초기화한다 - 모듈 전역이라 새어나가면 다른 테스트를 오염시킨다."""
    desktop.set_directory_picker(None)
    yield
    desktop.set_directory_picker(None)


@pytest.fixture
def unlocked_vault(tmp_path, monkeypatch):
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    monkeypatch.setattr(main, "VAULT", svc)
    main.vault_init(VaultInit(password=MASTER))
    return svc


def test_capabilities_report_no_picker_in_a_browser():
    assert main.desktop_capabilities().directory_picker is False


def test_capabilities_report_the_picker_once_the_shell_injects_it():
    desktop.set_directory_picker(lambda: "C:\repo\blog")

    assert main.desktop_capabilities().directory_picker is True


@pytest.mark.anyio
async def test_pick_directory_returns_501_without_a_desktop_shell(unlocked_vault):
    """브라우저에서 부르면 500 이 아니라 501 이어야 한다 - 고장이 아니라 미지원이다."""
    with pytest.raises(HTTPException) as e:
        await main.desktop_pick_directory()

    assert e.value.status_code == 501
    assert "직접 입력" in e.value.detail


@pytest.mark.anyio
async def test_pick_directory_returns_the_chosen_path(unlocked_vault):
    desktop.set_directory_picker(lambda: "C:\repo\blog")

    assert (await main.desktop_pick_directory()).path == "C:\repo\blog"


@pytest.mark.anyio
async def test_cancelling_the_dialog_is_not_an_error(unlocked_vault):
    """취소는 정상 흐름이다. 오류로 만들면 프론트가 쓸데없는 토스트를 띄운다."""
    desktop.set_directory_picker(lambda: None)

    assert (await main.desktop_pick_directory()).path is None


@pytest.mark.anyio
async def test_pick_directory_is_refused_while_the_vault_is_locked(unlocked_vault):
    """잠긴 상태에서 대화상자만 뜨는 건 쓸모도 없고(등록에 잠금 해제가 필요하다) 표면만 넓힌다."""
    desktop.set_directory_picker(lambda: "C:\repo\blog")
    main.vault_lock()

    with pytest.raises(HTTPException) as e:
        await main.desktop_pick_directory()

    assert e.value.status_code == 401


@pytest.fixture
def anyio_backend():
    return "asyncio"
