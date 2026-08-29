# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env 예외 계층.

전부 KeylensEnvError를 상속하므로 `except KeylensEnvError`로 한 번에 잡을 수도 있고,
필요하면 구체적인 타입으로 구분해서 잡을 수도 있다. 조용한 실패·빈 값 반환은 절대
하지 않는다 - 실패는 항상 이 계층의 예외로 표면화된다.

메시지 문구 규칙(중요): 사용자에게 보이는 메시지에는 **cp949로 인코딩할 수 없는 문자를
쓰지 않는다**. 한글 Windows 콘솔의 기본 stdout 인코딩이 cp949라, em dash(U+2014 `-`)
같은 문자가 들어가면 사용자가 `print(e)` 하는 순간 UnicodeEncodeError로 죽는다.
줄표가 필요하면 ASCII 하이픈(`-`)을 쓴다. `tests/test_messages.py`가 이를 강제한다.
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


class KeylensEmptyCollectionError(KeylensEnvError):
    """승인은 됐지만 그 컬렉션에 주입할 변수가 하나도 없음.

    조용히 빈 딕셔너리를 주입하고 성공한 척하면, 사용자는 한참 뒤에 엉뚱한 자리에서
    KeyError로 실패한다. 컬렉션 이름 오타나 "컬렉션 미지정으로 저장된 키"(등록일이
    컬렉션 이름이 되어 버린 경우)가 대부분의 원인이라, 그 자리에서 바로 알려준다.
    """
