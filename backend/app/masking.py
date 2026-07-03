# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""값 마스킹 — 앞부분(접두어 식별용)과 뒤 4자만 남기고 가린다."""
from __future__ import annotations

BULLET = "•"  # •


def mask(value: str, keep_front: int = 8, keep_back: int = 4) -> str:
    """가운데를 가린 마스킹 문자열을 만든다.

    >>> mask("sk-proj-aAbBcC1dDeE2fFgG3hIi4")
    'sk-proj-••••••••••••••••hIi4'
    """
    n = len(value)
    if n <= keep_back + 2:
        return BULLET * n
    front = min(keep_front, max(1, n - keep_back - 4))
    hidden = min(16, max(4, n - front - keep_back))
    return value[:front] + BULLET * hidden + value[-keep_back:]
