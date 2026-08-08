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


def test_flash_taskbar_absorbs_exception(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    # 이 테스트 호스트가 실제 Windows가 아니면 ctypes.windll 자체가 없어 AttributeError가
    # 나지만, try/except로 흡수되어 예외가 밖으로 새면 안 된다(실제 Windows에서는 창을
    # 못 찾아 hwnd=0 → 조용히 반환하는 경로를 탄다 — 두 경우 모두 예외 없이 끝나야 함).
    notify._flash_taskbar()


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
