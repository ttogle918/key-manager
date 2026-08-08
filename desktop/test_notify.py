# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 desktop/notify.py 유닛테스트 — 플랫폼 가드·예외 흡수만 검증.
OS 토스트·작업표시줄 깜빡임 자체는 수동 검증 대상(README 참고).
"""
import builtins
import sys

import notify


class FakeWindow:
    def __init__(self, raise_on_evaluate=False):
        self.calls = []
        self._raise = raise_on_evaluate

    def evaluate_js(self, script):
        self.calls.append(script)
        if self._raise:
            raise RuntimeError("boom")


def test_flash_taskbar_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    notify._flash_taskbar()  # 예외 없이 조용히 반환


# 이 테스트 호스트는 실제 Windows라서, sys.platform만 win32로 바꿔도 FindWindowW가
# 정상 호출되어 "KeyLens"라는 제목의 창이 없으므로 hwnd=0 → 조용한 조기 반환 경로만
# 타고, try 블록 안의 except Exception이 전혀 실행되지 않는다. except 분기를 실제로
# 검증하려면 ctypes.windll.user32.FindWindowW 자체가 예외를 던지도록 강제해야 한다.
def test_flash_taskbar_absorbs_exception_from_win32_api(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    import ctypes

    def boom(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr(ctypes.windll.user32, "FindWindowW", boom, raising=False)
    notify._flash_taskbar()  # 예외 없이 조용히 반환 — FindWindowW 실패도 흡수돼야 한다


def test_show_toast_absorbs_exception_when_plyer_missing(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "plyer":
            raise ImportError("plyer not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    notify._show_toast("블로그", "/repo/blog")  # 예외 없이 조용히 반환


def test_goto_pending_calls_evaluate_js():
    window = FakeWindow()
    notify._goto_pending(window)
    assert window.calls == ["window.__keylensGoPending && window.__keylensGoPending()"]


def test_goto_pending_absorbs_exception():
    window = FakeWindow(raise_on_evaluate=True)
    notify._goto_pending(window)  # RuntimeError 흡수, 밖으로 안 나옴


def test_build_notifier_calls_all_three_best_effort(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "_flash_taskbar", lambda *a, **k: calls.append("flash"))
    monkeypatch.setattr(
        notify, "_show_toast", lambda project, path: calls.append(("toast", project, path))
    )
    monkeypatch.setattr(notify, "_goto_pending", lambda w: calls.append(("goto", w)))

    window = FakeWindow()
    fn = notify.build_notifier(window)
    fn("블로그", "/repo/blog")

    assert calls == ["flash", ("toast", "블로그", "/repo/blog"), ("goto", window)]
