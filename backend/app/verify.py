# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""키 유효성 검증기 (TRUST-1) — 서비스의 read-only 엔드포인트를 1회 호출해 키 생사 확인.

설계 원칙
- **명시적 실행만**: 자동 주기 호출 없음. 사용자가 버튼을 눌렀을 때만 이 코드가 돈다.
- **read-only만**: 지식베이스가 선언한 GET/HEAD 만 허용(부수효과 있는 호출 차단).
- **값 비노출**: 키는 요청 헤더/쿼리에만 실리고, 반환값은 상태(active/invalid/unknown)뿐이다.
- **로컬 도구지만 외부 호출은 유일한 예외**: 검증은 해당 키의 원 서비스로만 나간다(사용자 소유 키·소유 서비스).
"""
from __future__ import annotations

from typing import Callable

from .models import VerifySpec

# fetch 시그니처: (method, url, headers, params) -> HTTP status code
Fetcher = Callable[[str, str, dict[str, str], dict[str, str]], int]

# 검증 호출 타임아웃(초) — 사용자가 버튼을 누르고 무한 대기하지 않도록 짧게.
TIMEOUT_SECONDS = 8.0


def build_request(
    spec: VerifySpec, value: str
) -> tuple[str, str, dict[str, str], dict[str, str]]:
    """VerifySpec + 키 값 → (method, url, headers, params).

    키를 어디에 싣는지는 spec.auth 로 결정한다. 값 자체는 로그로 남기지 않는다.
    """
    headers: dict[str, str] = dict(spec.extra_headers)
    params: dict[str, str] = {}

    if spec.auth == "bearer":
        headers["Authorization"] = f"Bearer {value}"
    elif spec.auth == "header":
        name = spec.header_name or "Authorization"
        headers[name] = f"{spec.prefix}{value}"
    elif spec.auth == "query":
        name = spec.query_name or "key"
        params[name] = value

    return spec.method, spec.url, headers, params


def classify_status(code: int) -> tuple[str, str]:
    """HTTP 상태코드 → (검증상태, 사람이 읽을 설명).

    - 2xx: 서비스가 키를 인정 → active
    - 401/403: 인증 거부 → invalid (폐기·오타)
    - 그 외(429·5xx 등): 판단 불가 → unknown (키 문제로 단정하지 않는다)
    """
    if 200 <= code < 300:
        return "active", f"HTTP {code} — 서비스가 키를 인정했습니다"
    if code in (401, 403):
        return "invalid", f"HTTP {code} — 인증 거부(폐기되었거나 잘못된 키)"
    if code == 429:
        return "unknown", "HTTP 429 — 요청이 제한되어 판단할 수 없습니다"
    return "unknown", f"HTTP {code} — 상태를 판단할 수 없습니다"


def _http_fetch(
    method: str, url: str, headers: dict[str, str], params: dict[str, str]
) -> int:
    """실제 네트워크 호출(표준 라이브러리 urllib). 테스트에선 가짜 fetcher 를 주입한다.

    새 의존성(httpx 등)을 쓰지 않는 이유: httpx 는 certifi(MPL-2.0)를 전이 의존으로
    끌고 온다 — 이 프로젝트의 permissive-only 규칙에 어긋난다. 표준 urllib 는 OS 신뢰
    저장소로 TLS 를 검증하므로 카피레프트 없이 검증 호출이 가능하다.
    """
    import urllib.error
    import urllib.parse
    import urllib.request

    if params:
        sep = "&" if urllib.parse.urlparse(url).query else "?"
        url = url + sep + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        # 4xx/5xx 는 예외로 오지만 우리에겐 정상 신호(예: 401=invalid).
        return e.code


def check_key(
    spec: VerifySpec, value: str, fetch: Fetcher | None = None
) -> tuple[str, str]:
    """키를 검증한다. 네트워크 오류·타임아웃은 unknown 으로 안전 처리(값은 절대 반환 안 함)."""
    method, url, headers, params = build_request(spec, value)
    caller = fetch or _http_fetch
    try:
        code = caller(method, url, headers, params)
    except Exception:  # noqa: BLE001 — 어떤 네트워크 예외든 키 문제로 단정하지 않는다
        return "unknown", "요청 실패(네트워크 오류·타임아웃) — 나중에 다시 시도하세요"
    return classify_status(code)
