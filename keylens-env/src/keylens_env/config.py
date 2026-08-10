# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""`.keylens.toml` 탐색 — python-dotenv의 find_dotenv()와 같은 방식으로 cwd(또는 지정한
시작 디렉토리)에서 상위로 올라가며 찾는다. 파일시스템 루트에 닿으면 중단한다.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from .exceptions import KeylensConfigError

CONFIG_FILENAME = ".keylens.toml"


def find_config(start: Path | None = None) -> tuple[str, Path]:
    """start(기본 Path.cwd())에서 상위로 .keylens.toml을 탐색해 (project, config_dir)을 반환한다.

    config_dir은 .keylens.toml이 실제로 위치한 디렉토리 — SDK 요청의 path 파라미터로 쓰인다
    (탐색을 시작한 start가 아니라, 실제로 찾은 위치가 프로젝트 루트이므로).
    """
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return _read_project(candidate), directory
    raise KeylensConfigError(
        f"{CONFIG_FILENAME}을(를) 찾을 수 없어요 — 프로젝트 루트에 만들거나 "
        "load_env(project=...)로 직접 지정하세요"
    )


def _read_project(path: Path) -> str:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise KeylensConfigError(f"{path}이(가) 올바른 TOML 형식이 아니에요: {e}") from e
    project = data.get("project")
    if not isinstance(project, str) or not project.strip():
        raise KeylensConfigError(f'{path}에 project 키가 없어요 — project = "이름" 을 추가하세요')
    return project
