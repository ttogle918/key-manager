# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""회귀 방지: 사용자에게 보이는 메시지가 한글 Windows 콘솔(cp949)에서 죽지 않아야 한다.

발단: 모든 에러 메시지에 em dash(U+2014)가 들어 있었는데 cp949에 그 문자가 없어서,
사용자가 README 예시대로 `except KeylensEnvError as e: print(e)` 를 하는 순간
UnicodeEncodeError 로 죽었다. 그것도 신규 사용자가 **가장 먼저** 만나는 승인 대기
에러에서. 소스의 메시지 문자열을 통째로 훑어 cp949 인코딩 가능 여부를 검사한다.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "keylens_env"
MODULES = sorted(SRC.glob("*.py"))


def _string_literals(path: pathlib.Path) -> list[str]:
    """모듈 안의 모든 문자열 리터럴(f-string 조각 포함). 독스트링·주석은 제외한다.

    독스트링은 print(e) 경로로 사용자에게 나가지 않으므로(그리고 이 레포의 한국어
    서술 스타일을 굳이 깨고 싶지 않으므로) 검사 대상에서 뺀다.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(doc)
    return [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in docstrings
    ]


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_messages_are_cp949_encodable(module: pathlib.Path) -> None:
    for text in _string_literals(module):
        try:
            text.encode("cp949")
        except UnicodeEncodeError as e:
            bad = text[e.start : e.end]
            pytest.fail(
                f"{module.name}: cp949로 인코딩할 수 없는 문자 {bad!r}(U+{ord(bad[0]):04X})가 "
                f"메시지에 있어요 - ASCII 하이픈 등으로 바꾸세요. 문제 문자열: {text!r}"
            )


def test_raised_exception_messages_survive_cp949() -> None:
    """실제로 던져지는 예외 메시지도 cp949로 출력 가능해야 한다(엔드투엔드 확인)."""
    from keylens_env import exceptions
    from keylens_env.client import _not_running_message

    messages = [
        _not_running_message(),
        "KeyLens 금고가 잠겨 있어요 - KeyLens 앱에서 잠금을 해제하세요.",
    ]
    for msg in messages:
        msg.encode("cp949")  # 예외가 나면 테스트 실패

    assert issubclass(exceptions.KeylensEmptyCollectionError, exceptions.KeylensEnvError)
