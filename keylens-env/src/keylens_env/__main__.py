# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""`python -m keylens_env` 커맨드라인.

    python -m keylens_env collections    # 쓸 수 있는 컬렉션 목록
    python -m keylens_env where          # 어떤 KeyLens 주소·컬렉션에 붙는지 진단

값은 절대 출력하지 않는다 - 이름과 개수만 보여준다(터미널 스크롤백·화면공유에 시크릿이
남지 않도록). 실패해도 traceback을 쏟지 않고 한 줄 메시지 + 종료 코드 1로 끝낸다.
"""
from __future__ import annotations

import sys
import unicodedata

from .client import resolve_base_url
from .config import CONFIG_FILENAME, find_config
from .exceptions import KeylensEnvError

_USAGE = "사용법: python -m keylens_env [collections|where]"


def _print(text: str) -> None:
    """한글 Windows 콘솔(cp949)에서 인코딩할 수 없는 문자가 섞여도 죽지 않게 출력한다."""
    enc = sys.stdout.encoding or "utf-8"
    sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + "\n")


def _width(text: str) -> int:
    """터미널 표시 폭. 한글·한자는 두 칸을 차지하므로 len()으로 정렬하면 어긋난다."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def _cmd_collections() -> int:
    from . import collections

    rows = collections()
    if not rows:
        _print("등록된 컬렉션이 없어요 - KeyLens 앱에서 키를 먼저 저장하세요.")
        return 0
    header = "컬렉션"
    width = max([_width(r.name) for r in rows] + [_width(header)])
    _print(f"{_pad(header, width)}  키 개수")
    _print(f"{'-' * width}  -------")
    for r in rows:
        _print(f"{_pad(r.name, width)}  {r.key_count}")
    return 0


def _cmd_where() -> int:
    _print(f"KeyLens 주소: {resolve_base_url()}")
    try:
        name, directory = find_config()
        _print(f"컬렉션      : {name}  ({directory / CONFIG_FILENAME})")
    except KeylensEnvError as e:
        _print(f"컬렉션      : (미설정) {e}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    command = args[0] if args else "collections"
    if command in ("-h", "--help", "help"):
        _print(_USAGE)
        return 0
    handlers = {"collections": _cmd_collections, "where": _cmd_where}
    handler = handlers.get(command)
    if handler is None:
        _print(f"알 수 없는 명령: {command}\n{_USAGE}")
        return 2
    try:
        return handler()
    except KeylensEnvError as e:
        _print(f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
