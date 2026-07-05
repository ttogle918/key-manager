# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""값 마스킹 — 앞부분(접두어 식별용)과 뒤 4자만 남기고 가린다."""
from __future__ import annotations

BULLET = "•"  # •


def mask(value: str, keep_front: int = 8, keep_back: int = 4) -> str:
    """가운데를 가린 마스킹 문자열을 만든다.

    keep_front 는 공개 정보인 접두어(sk- 등)를 식별용으로 남기기 위한 값이다.
    접두어가 없는 값(UUID·hex 등)은 호출부에서 keep_front 를 줄여 노출을 최소화한다.
    12자 미만의 짧은 값은 부분 노출만으로도 복원 여지가 커 전체를 가린다.

    >>> mask("sk-proj-aAbBcC1dDeE2fFgG3hIi4")
    'sk-proj-••••••••••••••••hIi4'
    >>> mask("shortpin7")
    '•••••••••'
    """
    n = len(value)
    if n < 12:
        return BULLET * n
    front = min(keep_front, max(1, n - keep_back - 4))
    hidden = min(16, max(4, n - front - keep_back))
    return value[:front] + BULLET * hidden + value[-keep_back:]
