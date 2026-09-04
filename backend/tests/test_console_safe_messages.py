# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""사용자에게 나가는 문자열이 한글 Windows 콘솔(cp949)에서 안전한지 검사한다.

왜 테스트로 박아 두나: em dash(U+2014)는 cp949 에 없어서, 그 문자가 든 메시지를 출력하는
순간 UnicodeEncodeError 로 **프로세스가 죽는다**. HTTP 응답(UTF-8 JSON)으로는 문제가 없어
눈에 잘 안 띄지만, 이 문자열들은 keylens-env SDK 와 CLI 를 거쳐 사용자의 터미널로 나가고
트레이스백에도 실린다. 실제로 개발 중 이 문자 때문에 파이썬 프로세스가 죽는 걸 겪었다.

검사 대상은 "사용자에게 나가는 문자열"로 한정한다 - 예외 생성자의 인자와 HTTPException 의
detail. 주석·docstring 은 콘솔로 나가지 않으므로 건드리지 않는다.
"""
import ast
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
ROOTS = ["backend/app", "manager-relay/app", "keylens-env/src"]


def _user_facing_strings(path: pathlib.Path):
    """(줄번호, 문자열) - 예외 인자와 HTTPException(detail=...) 만."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        values = list(node.args) + [k.value for k in node.keywords if k.arg == "detail"]
        for arg in values:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                yield node.lineno, arg.value
            elif isinstance(arg, ast.JoinedStr):  # f-string 의 리터럴 조각
                for v in arg.values:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        yield node.lineno, v.value


def _sources():
    for root in ROOTS:
        base = REPO / root
        if base.exists():
            yield from sorted(base.rglob("*.py"))


@pytest.mark.parametrize("path", list(_sources()), ids=lambda p: p.name)
def test_user_facing_strings_encode_in_cp949(path):
    offenders = []
    for lineno, text in _user_facing_strings(path):
        try:
            text.encode("cp949")
        except UnicodeEncodeError as e:
            offenders.append((lineno, e.object[e.start : e.end]))

    assert not offenders, (
        f"{path.relative_to(REPO)} 에 cp949 로 출력할 수 없는 문자가 있습니다: {offenders}. "
        "em dash(-)는 ASCII 하이픈으로 바꾸세요 - 한글 콘솔에서 프로세스가 죽습니다."
    )
