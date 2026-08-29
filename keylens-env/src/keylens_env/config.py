# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""`.keylens.toml` 탐색 - python-dotenv의 find_dotenv()와 같은 방식으로 cwd(또는 지정한
시작 디렉토리)에서 상위로 올라가며 찾는다. 파일시스템 루트에 닿으면 중단한다.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from .exceptions import KeylensConfigError

CONFIG_FILENAME = ".keylens.toml"


def find_config(start: Path | None = None) -> tuple[str, Path]:
    """start(기본 Path.cwd())에서 상위로 .keylens.toml을 탐색해 (collection, config_dir)을 반환한다.

    config_dir은 .keylens.toml이 실제로 위치한 디렉토리 - SDK 요청의 path 파라미터로 쓰인다
    (탐색을 시작한 start가 아니라, 실제로 찾은 위치가 프로젝트 루트이므로).
    """
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return _read_project(candidate), directory
    raise KeylensConfigError(
        f"{CONFIG_FILENAME}을(를) 찾을 수 없어요 - 프로젝트 루트에 만들거나 "
        "load_env(collection=...)로 직접 지정하세요"
    )


def _read_text(path: Path) -> str:
    """설정 파일을 읽는다. Windows 메모장이 붙이는 BOM까지 흡수한다.

    `utf-8-sig`는 BOM이 있으면 떼어내고 없으면 utf-8과 동일하게 동작한다 - BOM 때문에
    "TOML 형식이 아니에요"라는 엉뚱한 오류가 나던 문제를 없앤다. UTF-16(메모장의
    '유니코드' 저장)처럼 아예 다른 인코딩이면 원시 UnicodeDecodeError가 밖으로 새지
    않도록 여기서 KeylensConfigError로 바꿔 준다.
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as e:
        raise KeylensConfigError(
            f"{path}을(를) UTF-8로 읽을 수 없어요 - 메모장의 '유니코드'(UTF-16) 대신 "
            "'UTF-8'로 다시 저장하세요"
        ) from e
    except OSError as e:
        raise KeylensConfigError(f"{path}을(를) 읽을 수 없어요: {e}") from e


def _read_project(path: Path) -> str:
    try:
        data = tomllib.loads(_read_text(path))
    except tomllib.TOMLDecodeError as e:
        raise KeylensConfigError(f"{path}이(가) 올바른 TOML 형식이 아니에요: {e}") from e
    # `collection`을 우선하고, 예전 문서대로 쓴 `project`도 계속 받아 준다(하위 호환).
    value = data.get("collection", data.get("project"))
    if not isinstance(value, str) or not value.strip():
        raise KeylensConfigError(
            f'{path}에 collection 키가 없어요 - collection = "이름" 을 추가하세요'
        )
    return value.strip()
