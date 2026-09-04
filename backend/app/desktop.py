# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""데스크톱 셸(pywebview)만 할 수 있는 일을 백엔드에 꽂아 두는 자리.

브라우저에서는 웹 표준이 보안상 절대경로를 주지 않아 폴더 선택을 구현할 수 없다. 반면
데스크톱 앱은 네이티브 대화상자를 띄울 수 있다. 그 차이를 백엔드가 **기능 유무**로만
표현하고(has_directory_picker), 실제 구현은 desktop/app.py 가 주입한다 - 백엔드가
pywebview 를 import 하지 않아야 브라우저 개발 모드와 테스트가 GUI 없이 그대로 돈다
(VaultService.set_pending_hook 과 같은 패턴).
"""
from __future__ import annotations

from typing import Callable

# 폴더 하나를 고르게 하고 절대경로를 돌려준다. 사용자가 취소하면 None.
DirectoryPicker = Callable[[], "str | None"]

_picker: DirectoryPicker | None = None


class DirectoryPickerUnavailable(RuntimeError):
    """데스크톱 셸이 아니라 폴더 선택창을 띄울 수 없다."""


def set_directory_picker(fn: DirectoryPicker | None) -> None:
    global _picker
    _picker = fn


def has_directory_picker() -> bool:
    return _picker is not None


def pick_directory() -> str | None:
    """폴더 선택창을 띄우고 고른 절대경로를 돌려준다. 취소하면 None."""
    if _picker is None:
        raise DirectoryPickerUnavailable(
            "폴더 찾기는 데스크톱 앱에서만 됩니다 - 경로를 직접 입력하세요"
        )
    return _picker()
