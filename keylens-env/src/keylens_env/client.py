# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 로컬 백엔드로 HTTP 호출 — 표준 라이브러리 urllib.request만 쓴다(새 의존성 0).

상태 코드 → 예외 매핑은 이 파일 한 곳에서만 한다 — 백엔드가 상태 코드를 바꾸면 여기만 고치면 된다.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .exceptions import (
    KeylensApprovalPendingError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)

DEFAULT_BASE_URL = "http://127.0.0.1:8765"
_TIMEOUT_SECONDS = 5.0


def fetch_env(project: str, path: str, base_url: str = DEFAULT_BASE_URL) -> dict[str, str]:
    """POST {base_url}/sdk/env — 성공 시 {official_env_name: value} 딕셔너리를 반환한다.

    실패는 절대 조용히 넘어가지 않고 타입이 다른 예외로 정규화한다:
    - 연결 자체가 안 됨(KeyLens 꺼짐/주소 다름) → KeylensNotRunningError
    - 401(잠김) → KeylensLockedError
    - 403(미승인) → KeylensApprovalPendingError
    - 그 외 오류 상태(예: 422 복호화 실패) → KeylensServerError
    """
    body = json.dumps({"project": project, "path": path}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/sdk/env",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as res:
            payload = json.loads(res.read().decode("utf-8"))
            return payload["values"]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise KeylensLockedError(
                "KeyLens 금고가 잠겨 있어요 — KeyLens 앱에서 잠금을 해제하세요"
            ) from None
        if e.code == 403:
            raise KeylensApprovalPendingError(
                f"'{path}'가 '{project}' 프로젝트 키를 요청했어요 — "
                "KeyLens 앱의 '승인 대기' 화면에서 허용해 주세요"
            ) from None
        raise KeylensServerError(
            f"KeyLens가 예상치 못한 응답을 반환했어요(HTTP {e.code})"
        ) from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise KeylensNotRunningError(
            f"{base_url}에서 KeyLens를 찾을 수 없어요 — KeyLens 앱을 켜고 잠금을 해제하세요"
        ) from None
