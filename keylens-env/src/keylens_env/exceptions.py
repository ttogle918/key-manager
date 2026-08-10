# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env 예외 계층.

전부 KeylensEnvError를 상속하므로 `except KeylensEnvError`로 한 번에 잡을 수도 있고,
필요하면 구체적인 타입으로 구분해서 잡을 수도 있다. 조용한 실패·빈 값 반환은 절대
하지 않는다 — 실패는 항상 이 계층의 예외로 표면화된다.
"""
from __future__ import annotations


class KeylensEnvError(Exception):
    """모든 keylens-env 예외의 베이스."""


class KeylensNotRunningError(KeylensEnvError):
    """KeyLens 앱에 연결할 수 없음(꺼져 있거나 접속 주소가 다름)."""


class KeylensLockedError(KeylensEnvError):
    """KeyLens 금고가 잠겨 있음(401)."""


class KeylensApprovalPendingError(KeylensEnvError):
    """이 디렉토리의 접근 요청이 KeyLens에서 아직 승인되지 않음(403)."""


class KeylensConfigError(KeylensEnvError):
    """`.keylens.toml`을 찾지 못했거나 형식이 잘못됨, 혹은 project 인자도 없음."""


class KeylensServerError(KeylensEnvError):
    """KeyLens가 예상치 못한 응답을 반환함(401/403이 아닌 다른 오류 상태)."""
