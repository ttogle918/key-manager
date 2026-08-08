# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 desktop/notify.py 유닛테스트 — 플랫폼 가드·예외 흡수만 검증.
OS 토스트·작업표시줄 깜빡임 자체는 수동 검증 대상(README 참고).
"""
import builtins
import sys
import threading
import time

import pytest

import notify


class FakeWindow:
    def __init__(self, raise_on_evaluate=False, delay=0.0):
        self.calls = []
        self._raise = raise_on_evaluate
        self._delay = delay

    def evaluate_js(self, script):
        self.calls.append(script)
        if self._delay:
            time.sleep(self._delay)
        if self._raise:
            raise RuntimeError("boom")


def test_flash_taskbar_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    notify._flash_taskbar()  # 예외 없이 조용히 반환


# 이 테스트 호스트는 실제 Windows라서, sys.platform만 win32로 바꿔도 FindWindowW가
# 정상 호출되어 "KeyLens"라는 제목의 창이 없으므로 hwnd=0 → 조용한 조기 반환 경로만
# 타고, try 블록 안의 except Exception이 전혀 실행되지 않는다. except 분기를 실제로
# 검증하려면 ctypes.windll.user32.FindWindowW 자체가 예외를 던지도록 강제해야 한다.
# ctypes.windll은 Windows에만 존재하므로, 비Windows 호스트에서는 이 테스트 자체의
# 셋업(monkeypatch.setattr(ctypes.windll...))이 코드 자체가 아니라 AttributeError로
# 죽는다 — sibling test_flash_taskbar_noop_on_non_windows처럼 깔끔히 건너뛰어야 한다.
@pytest.mark.skipif(sys.platform != "win32", reason="ctypes.windll only exists on Windows")
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
    # notify() now runs the actual work on a background daemon thread (see
    # test_build_notifier_returns_promptly_even_if_window_blocks below for why), so this
    # test can't assert `calls` immediately after fn(...) returns — it has to wait
    # deterministically for the background thread to finish via a threading.Event set on
    # the last step, instead of a bare sleep-and-hope.
    calls = []
    done = threading.Event()
    monkeypatch.setattr(notify, "_flash_taskbar", lambda *a, **k: calls.append("flash"))
    monkeypatch.setattr(
        notify, "_show_toast", lambda project, path: calls.append(("toast", project, path))
    )

    def fake_goto(w):
        calls.append(("goto", w))
        done.set()

    monkeypatch.setattr(notify, "_goto_pending", fake_goto)

    window = FakeWindow()
    fn = notify.build_notifier(window)
    fn("블로그", "/repo/blog")

    assert done.wait(timeout=2.0), "background notification work never completed"
    assert calls == ["flash", ("toast", "블로그", "/repo/blog"), ("goto", window)]


def test_build_notifier_returns_promptly_even_if_window_blocks(monkeypatch):
    """notify()가 window.evaluate_js처럼 블로킹할 수 있는 호출을 백그라운드 스레드로
    돌리고 즉시 반환하는지 검증 — 이게 이번 수정의 핵심(20초까지 블로킹 가능한
    evaluate_js가 SDK 요청 처리 스레드를 막으면 안 된다)."""
    window = FakeWindow(delay=0.3)  # evaluate_js가 0.3초 블로킹한다고 가정
    done = threading.Event()
    real_goto = notify._goto_pending

    def goto_then_signal(w):
        real_goto(w)  # 실제 _goto_pending 로직(그대로 유지) 실행
        done.set()

    monkeypatch.setattr(notify, "_flash_taskbar", lambda *a, **k: None)
    monkeypatch.setattr(notify, "_show_toast", lambda *a, **k: None)
    monkeypatch.setattr(notify, "_goto_pending", goto_then_signal)

    fn = notify.build_notifier(window)

    start = time.perf_counter()
    fn("블로그", "/repo/blog")
    elapsed = time.perf_counter() - start

    assert elapsed < 0.05, f"notify() blocked the caller for {elapsed:.3f}s instead of returning immediately"

    # 반환은 즉시 됐어야 하지만, 백그라운드 작업 자체는 실제로 일어나야 한다 —
    # Event로 완료를 기다려 deterministic하게 확인(bare sleep-and-hope 금지).
    assert done.wait(timeout=2.0), "background notification work never completed"
    assert window.calls == ["window.__keylensGoPending && window.__keylensGoPending()"]
