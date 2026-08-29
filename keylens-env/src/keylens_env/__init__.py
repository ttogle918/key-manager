# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env - dotenv 대체 런타임 SDK.

실행 중이고 잠금 해제된 KeyLens 로컬 백엔드에서 값을 받아 os.environ에 주입한다.
디스크에 평문 .env 파일을 남기지 않는다. 자체 암호화·인증 로직은 없다 - KeyLens 앱이
켜져 있고 잠금 해제된 상태에서만 동작한다.

용어: 키 묶음은 앱 화면·문서·이 패키지에서 모두 **컬렉션(collection)**이라고 부른다.
백엔드 HTTP 필드명과 DB 컬럼만 옛 이름 `project`를 유지한다(이 패키지가 다른 레포에
버전 고정으로 설치되므로 와이어 포맷을 바꾸면 버전 스큐가 난다). 옛 이름으로 쓰던
코드도 계속 동작한다: `.keylens.toml`의 `project` 키, `load_env(project=...)`.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

from . import client
from .client import CANDIDATE_BASE_URLS, DEFAULT_BASE_URL, fetch_collections, fetch_env
from .config import find_config
from .exceptions import (
    KeylensApprovalPendingError,
    KeylensConfigError,
    KeylensEmptyCollectionError,
    KeylensEnvError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)

__version__ = "0.2.0"

__all__ = [
    "load_env",
    "collections",
    "Collection",
    "KeylensEnvError",
    "KeylensNotRunningError",
    "KeylensLockedError",
    "KeylensApprovalPendingError",
    "KeylensConfigError",
    "KeylensEmptyCollectionError",
    "KeylensServerError",
]


class Collection(NamedTuple):
    """KeyLens에 등록된 키 묶음 하나. `name`으로 load_env(collection=name)에 넘기면 된다."""

    name: str
    key_count: int


def collections() -> list[Collection]:
    """KeyLens에 있는 컬렉션 목록을 [Collection(name, key_count), ...]으로 반환한다.

    무엇을 쓸 수 있는지 확인하는 용도라 **금고가 잠겨 있어도** 조회된다(이름과 개수만
    나오고 값은 나오지 않는다). 이름이 `2026-08-29`처럼 날짜인 항목은 KeyLens에서
    컬렉션을 지정하지 않고 저장한 키들이 등록일로 묶인 것이다.

    터미널에서 바로 보고 싶으면: `python -m keylens_env collections`
    """
    return [Collection(r["project"], r["key_count"]) for r in fetch_collections()]


def load_env(
    collection: str | None = None,
    *,
    project: str | None = None,
    override: bool = True,
) -> dict[str, str]:
    """KeyLens 금고에서 값을 받아 os.environ에 주입하고, 주입한 {이름: 값}을 반환한다.

    collection을 생략하면 cwd에서 상위로 `.keylens.toml`을 탐색해 결정한다
    (python-dotenv의 .env 탐색과 같은 방식). 명시하면 탐색을 건너뛰고 cwd를 그대로
    승인 경로(path)로 쓴다 - 이 경우 **스크립트를 실행하는 디렉토리마다 따로 승인**이
    필요하니, 보통은 `.keylens.toml` 방식이 편하다.

    override=False면 이미 os.environ에 있는 변수는 건드리지 않는다(python-dotenv의
    기본값과 같은 동작). 기본값은 True - 금고를 단일 진실 공급원으로 두는 쪽이다.

    실패 시 절대 조용히 넘어가지 않는다 - KeylensEnvError 계열 예외를 그대로 던진다.
    승인은 됐는데 주입할 변수가 하나도 없는 경우도 실패로 본다
    (KeylensEmptyCollectionError) - 빈 주입은 한참 뒤 엉뚱한 자리에서 KeyError로 터진다.
    """
    name = collection if collection is not None else project
    if name is not None:
        resolved = name
        request_path = str(Path.cwd().resolve())
    else:
        resolved, config_dir = find_config()
        request_path = str(config_dir)

    values = fetch_env(resolved, request_path)
    if not values:
        raise KeylensEmptyCollectionError(
            f"'{resolved}' 컬렉션에 주입할 변수가 없어요 - 이름이 맞는지, KeyLens에서 그 "
            f"키들의 컬렉션이 '{resolved}'로 지정돼 있는지 확인하세요(컬렉션을 지정하지 "
            "않고 저장한 키는 등록일 이름으로 묶입니다). 쓸 수 있는 목록은 "
            "`python -m keylens_env collections`로 볼 수 있어요"
        )
    injected = values if override else {k: v for k, v in values.items() if k not in os.environ}
    os.environ.update(injected)
    return injected
