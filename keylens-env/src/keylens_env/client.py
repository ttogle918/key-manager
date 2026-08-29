# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 로컬 백엔드로 HTTP 호출 - 표준 라이브러리 urllib.request만 쓴다(새 의존성 0).

상태 코드 -> 예외 매핑은 이 파일 한 곳에서만 한다(백엔드가 상태 코드를 바꾸면 여기만 고친다).
응답 본문이 KeyLens가 아닌 다른 프로그램의 것이거나 형식이 어긋나도 여기서 전부
KeylensEnvError 계열로 정규화한다 - 이 모듈 밖으로 urllib/json의 원시 예외가 새면 안 된다.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .exceptions import (
    KeylensApprovalPendingError,
    KeylensLockedError,
    KeylensNotRunningError,
    KeylensServerError,
)

# 데스크톱 exe 기본 포트. 개발 모드(scripts/dev.mjs)는 8003을 쓰므로 둘 다 후보로 둔다.
DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEV_BASE_URL = "http://127.0.0.1:8003"
CANDIDATE_BASE_URLS = (DEFAULT_BASE_URL, DEV_BASE_URL)

_TIMEOUT_SECONDS = 5.0
_PROBE_TIMEOUT_SECONDS = 1.5

# 탐색 결과 프로세스 캐시 - load_env()를 여러 번 불러도 /health 왕복은 한 번만.
_resolved_base_url: str | None = None


def _request(url: str, payload: dict | None, timeout: float):
    """JSON 요청/응답 한 번. 파싱된 JSON을 그대로 반환한다(객체일 수도, 배열일 수도 있다).

    HTTPError는 그대로 올려보내고(호출자가 상태별로 처리), 그 외 실패는 전부
    KeylensEnvError 계열로 정규화한다.
    """
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
    except urllib.error.HTTPError:
        raise  # 상태 코드별 처리는 호출자 몫
    except (urllib.error.URLError, OSError, TimeoutError):
        raise KeylensNotRunningError(_not_running_message()) from None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        # 그 주소에 KeyLens가 아닌 다른 프로그램이 떠 있는 경우가 대부분이다.
        raise KeylensServerError(
            f"{url}이(가) KeyLens 응답이 아닌 값을 돌려줬어요 - 그 포트를 다른 프로그램이 "
            "쓰고 있는지 확인하거나, KEYLENS_BASE_URL로 주소를 직접 지정하세요"
        ) from None


def _not_running_message() -> str:
    override = os.environ.get("KEYLENS_BASE_URL")
    if override:
        return (
            f"{override}에서 KeyLens를 찾을 수 없어요 - KEYLENS_BASE_URL 주소가 맞는지 "
            "확인하고, KeyLens 앱을 켠 뒤 잠금을 해제하세요"
        )
    tried = ", ".join(CANDIDATE_BASE_URLS)
    return (
        f"KeyLens를 찾을 수 없어요(시도한 주소: {tried}) - KeyLens 앱을 켜고 잠금을 "
        "해제하세요. 다른 포트로 띄웠다면 KEYLENS_BASE_URL로 주소를 지정하세요"
    )


def _looks_like_keylens(payload) -> bool:
    """/health 응답이 KeyLens의 것인지 확인 - 같은 포트를 쓰는 남의 앱을 걸러낸다."""
    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and "services" in payload
        and "credentials" in payload
    )


def resolve_base_url(*, force: bool = False) -> str:
    """실제로 쓸 KeyLens 주소를 정한다.

    KEYLENS_BASE_URL이 있으면 그 값을 그대로 쓴다(탐색하지 않는다 - 사용자가 명시한 주소를
    말없이 다른 포트로 바꿔치기하면 안 되므로). 없으면 후보 주소(exe 8765 -> dev 8003)를
    순서대로 /health로 찔러 보고 **KeyLens가 맞는 첫 주소**를 고른다. 결과는 프로세스에
    캐시한다. force=True면 캐시를 무시하고 다시 탐색한다(테스트용).
    """
    global _resolved_base_url
    override = os.environ.get("KEYLENS_BASE_URL")
    if override:
        return override.rstrip("/")
    if _resolved_base_url is not None and not force:
        return _resolved_base_url
    for base in CANDIDATE_BASE_URLS:
        try:
            payload = _request(f"{base}/health", None, _PROBE_TIMEOUT_SECONDS)
        except (urllib.error.HTTPError, KeylensNotRunningError, KeylensServerError):
            continue
        if _looks_like_keylens(payload):
            _resolved_base_url = base
            return base
    raise KeylensNotRunningError(_not_running_message())


def _post(path: str, payload: dict, base_url: str | None):
    base = (base_url or resolve_base_url()).rstrip("/")
    return _request(f"{base}{path}", payload, _TIMEOUT_SECONDS)


def fetch_env(project: str, path: str, base_url: str | None = None) -> dict[str, str]:
    """POST /sdk/env - 성공 시 {official_env_name: value} 딕셔너리를 반환한다.

    실패는 절대 조용히 넘어가지 않고 타입이 다른 예외로 정규화한다:
    - 연결 자체가 안 됨(KeyLens 꺼짐/주소 다름) -> KeylensNotRunningError
    - 401(잠김) -> KeylensLockedError
    - 403(미승인) -> KeylensApprovalPendingError
    - 그 외 오류 상태(예: 422 복호화 실패)·형식 불일치 -> KeylensServerError
    """
    try:
        payload = _post("/sdk/env", {"project": project, "path": path}, base_url)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise KeylensLockedError(
                "KeyLens 금고가 잠겨 있어요 - KeyLens 앱에서 잠금을 해제하세요. "
                "(무활동 5분이면 자동으로 잠깁니다. KEYLENS_AUTOLOCK_SECONDS로 조정할 수 있어요)"
            ) from None
        if e.code == 403:
            raise KeylensApprovalPendingError(
                f"'{path}'가 '{project}' 컬렉션의 키를 요청했어요 - "
                "KeyLens 앱의 '승인 대기' 화면에서 허용해 주세요"
            ) from None
        raise KeylensServerError(
            f"KeyLens가 예상치 못한 응답을 반환했어요(HTTP {e.code})"
        ) from None
    values = payload.get("values") if isinstance(payload, dict) else None
    if not isinstance(values, dict):
        raise KeylensServerError(
            "KeyLens 응답에 values가 없어요 - KeyLens 앱과 keylens-env 버전이 맞는지 확인하세요"
        )
    return {str(k): str(v) for k, v in values.items()}


def fetch_collections(base_url: str | None = None) -> list[dict]:
    """GET /sdk/projects - [{"project": 이름, "key_count": 개수}] 목록을 반환한다.

    값을 다루지 않으므로 금고가 잠겨 있어도 조회된다(무엇을 쓸 수 있는지 확인하는 용도).
    """
    base = (base_url or resolve_base_url()).rstrip("/")
    try:
        raw = _request(f"{base}/sdk/projects", None, _TIMEOUT_SECONDS)
    except urllib.error.HTTPError as e:
        raise KeylensServerError(
            f"KeyLens가 예상치 못한 응답을 반환했어요(HTTP {e.code})"
        ) from None
    if not isinstance(raw, list) or not all(isinstance(r, dict) for r in raw):
        raise KeylensServerError(
            "KeyLens 컬렉션 목록 응답 형식이 맞지 않아요 - KeyLens 앱과 keylens-env "
            "버전이 맞는지 확인하세요"
        )
    return [
        {"project": str(r.get("project", "")), "key_count": int(r.get("key_count") or 0)}
        for r in raw
    ]
