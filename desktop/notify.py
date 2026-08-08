# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 데스크톱 승인 알림 — 작업표시줄 깜빡임 + OS 토스트 + SPA 화면 전환.

전부 best-effort: 어느 하나가 실패해도 SDK 요청 흐름에 영향을 주지 않는다(그래서
build_notifier()의 결과를 VaultService.set_pending_hook()에 그대로 연결해도 안전하다).
사용자는 최소한 PendingScreen의 화면 안 배너로 뒤늦게라도 확인할 수 있다.
"""
from __future__ import annotations

import sys
import threading
from typing import Callable, Protocol


class _Window(Protocol):
    """pywebview 창 객체 중 이 모듈이 실제로 쓰는 부분만의 최소 인터페이스."""

    def evaluate_js(self, script: str) -> object: ...


def _flash_taskbar(title: str = "KeyLens") -> None:
    """작업표시줄 아이콘 깜빡임(Windows만, FlashWindowEx). 창을 제목으로 찾는다 —
    pywebview 내부 GUI 백엔드 구현에 의존하지 않기 위함. 실패하면 조용히 무시."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if not hwnd:
            return

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        flashw_tray = 0x00000002
        flashw_timernofg = 0x0000000C
        info = FLASHWINFO(
            cbSize=ctypes.sizeof(FLASHWINFO),
            hwnd=hwnd,
            dwFlags=flashw_tray | flashw_timernofg,
            uCount=5,
            dwTimeout=0,
        )
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


def _show_toast(project: str, path: str) -> None:
    """OS 토스트(정보 제공용, 클릭 동작 없음). 실패하면 조용히 무시."""
    try:
        from plyer import notification

        notification.notify(
            title="KeyLens — 승인 대기",
            message=f"'{path}'가 '{project}' 프로젝트 키를 요청했어요",
            app_name="KeyLens",
            timeout=6,
        )
    except Exception:
        pass


def _goto_pending(window: _Window) -> None:
    """이미 떠 있는 SPA를 승인 대기 화면으로 즉시 전환. 실패하면 조용히 무시."""
    try:
        window.evaluate_js("window.__keylensGoPending && window.__keylensGoPending()")
    except Exception:
        pass


def build_notifier(window: _Window, title: str = "KeyLens") -> Callable[[str, str], None]:
    """VaultService.set_pending_hook()에 넘길 콜백을 만든다.

    반환한 함수는 무엇이 실패해도 절대 예외를 던지지 않는다 — 호출부인
    VaultService.sdk_env가 이 훅의 실패로 SDK 요청 자체를 깨뜨리면 안 되기 때문.

    실제 알림 작업(_flash_taskbar/_show_toast/_goto_pending)은 짧게 사는 데몬 스레드에서
    돌리고 즉시 반환한다 — _goto_pending의 evaluate_js가 실제 pywebview에서 웹뷰가 아직
    준비되지 않았을 때 최대 ~20초까지 블로킹할 수 있는데, sdk_env()가 sqlite 연결을 쥔 채
    요청 처리 스레드에서 이 훅을 동기 호출하므로, 여기서 블로킹하면 SDK 요청(POST /sdk/env)
    자체가 그만큼 멎어버린다(플랜의 best-effort 원칙 위반).
    """

    def _run(project: str, path: str) -> None:
        _flash_taskbar(title)
        _show_toast(project, path)
        _goto_pending(window)

    def notify(project: str, path: str) -> None:
        try:
            threading.Thread(target=_run, args=(project, path), daemon=True).start()
        except Exception:
            pass  # 스레드 기동 자체가 실패해도(예: 스레드 고갈) SDK 요청은 계속 진행

    return notify
