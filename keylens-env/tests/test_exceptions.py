# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""예외 계층 — 전부 KeylensEnvError를 상속해 한 번에 잡을 수 있어야 한다."""
import pytest

from keylens_env.exceptions import (
    KeylensApprovalPendingError,
    KeylensConfigError,
    KeylensEnvError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)


@pytest.mark.parametrize(
    "exc_cls",
    [
        KeylensNotRunningError,
        KeylensLockedError,
        KeylensApprovalPendingError,
        KeylensConfigError,
        KeylensServerError,
    ],
)
def test_specific_exceptions_are_keylens_env_error(exc_cls):
    assert issubclass(exc_cls, KeylensEnvError)


def test_keylens_env_error_is_exception():
    assert issubclass(KeylensEnvError, Exception)


def test_exceptions_carry_message():
    err = KeylensLockedError("금고가 잠겨 있어요")
    assert str(err) == "금고가 잠겨 있어요"
