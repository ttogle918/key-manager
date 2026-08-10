# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""keylens-env — dotenv 대체 런타임 SDK.

실행 중이고 잠금 해제된 KeyLens 로컬 백엔드에서 값을 받아 os.environ에 주입한다.
디스크에 평문 .env 파일을 남기지 않는다. 자체 암호화·인증 로직은 없다 — KeyLens 앱이
켜져 있고 잠금 해제된 상태에서만 동작한다.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import client
from .client import DEFAULT_BASE_URL, fetch_env
from .config import find_config
from .exceptions import (
    KeylensApprovalPendingError,
    KeylensConfigError,
    KeylensEnvError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)

__version__ = "0.1.0"

__all__ = [
    "load_env",
    "KeylensEnvError",
    "KeylensNotRunningError",
    "KeylensLockedError",
    "KeylensApprovalPendingError",
    "KeylensConfigError",
    "KeylensServerError",
]


def load_env(project: str | None = None) -> None:
    """KeyLens 금고에서 값을 받아 os.environ에 주입한다.

    project를 생략하면 cwd에서 상위로 .keylens.toml을 탐색해 project를 정한다
    (python-dotenv의 .env 탐색과 같은 방식). project를 명시하면 탐색을 건너뛰고
    cwd를 그대로 승인 경로(path)로 쓴다.

    실패 시 절대 조용히 넘어가지 않는다 — KeylensEnvError 계열 예외를 그대로 던진다.
    """
    if project is not None:
        resolved_project = project
        request_path = str(Path.cwd().resolve())
    else:
        resolved_project, config_dir = find_config()
        request_path = str(config_dir)

    base_url = os.environ.get("KEYLENS_BASE_URL", DEFAULT_BASE_URL)
    values = fetch_env(resolved_project, request_path, base_url=base_url)
    os.environ.update(values)
