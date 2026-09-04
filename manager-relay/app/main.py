# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 매니저 릴레이 API.

계정·DB 없이 SMTP로만 암호화 금고 번들을 목적지 이메일로 전달한다. 번들의 비밀 값은
암호화되어 있지만, service·label·project·memo 같은 메타데이터는 평문으로 포함되어
있어 이 릴레이를 운영하는 매니저와 그의 메일 제공자가 볼 수 있다. 이 서버는 요청 처리가
끝나면 프로세스 메모리에 아무것도 영구 저장하지 않는다(다만 SMTP 발송분은 매니저의
메일함 "보낸 편지함"에 남을 수 있다 —
docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md).
"""
from __future__ import annotations

import html
import json
import os
import urllib.parse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from .mailer import MailSendError, SmtpConfig, send_bundle_email, send_confirm_email
from .models import SyncRequestBody
from .rate_limit import RateLimitExceeded, RateLimiter
from .token_store import TokenStore

app = FastAPI(title="KeyLens Manager Relay", version="0.1.0")

# 실제 번들은 수 KB 수준이다 — 이보다 훨씬 큰 요청은 형식이 잘못됐거나(공격) 남용 시도로
# 간주해 pydantic이 전체를 메모리로 파싱하기 전에 미들웨어에서 먼저 거부한다.
#
# 이 미들웨어는 반드시 아래의 CORSMiddleware 등록보다 먼저 등록해야 한다. Starlette은
# add_middleware 호출마다 리스트 맨 앞에 끼워 넣고, 스택은 그 리스트를 reversed()로 감싸
# 만들기 때문에 "나중에 등록된 것이 가장 바깥"이 된다. 즉 이 함수가 CORS보다 먼저 등록돼야
# CORS가 가장 바깥으로 와서 이 미들웨어가 반환하는 413 응답에도 CORS 헤더가 붙는다 — 순서가
# 반대면 413 응답이 CORSMiddleware를 거치지 않아 브라우저 fetch()가 CORS 오류로 실패해
# "용량 초과" 대신 "연결할 수 없음" 같은 엉뚱한 에러로 보인다.
MAX_REQUEST_BYTES = 1_000_000


@app.middleware("http")
async def _reject_oversized_requests(request: Request, call_next):
    if request.method == "POST" and request.url.path == "/sync/request":
        content_length = request.headers.get("content-length")
        if content_length is not None and int(content_length) > MAX_REQUEST_BYTES:
            return Response(content="금고 번들이 너무 커요", status_code=413)
    return await call_next(request)


# 이 릴레이는 자격증명을 쓰지 않는 공개 API라, 배포되는 exe가 어떤 로컬 오리진에서
# 오든(사용자마다 포트가 다를 수 있음) 그대로 허용한다. 쿠키/세션이 없어 안전하다.
# (등록 순서 주의사항은 위의 MAX_REQUEST_BYTES 주석 참고 — 반드시 이 CORSMiddleware가
# _reject_oversized_requests보다 나중에 등록돼야 한다.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# 기동 시 SMTP 설정이 없으면 바로 실패한다(fail-fast) — 자격증명 없이 조용히 떠서
# "되는 척"하지 않는다.
SMTP = SmtpConfig.from_env()
STORE = TokenStore()

_int = lambda k, d: int(os.environ.get(k, d))  # noqa: E731
# 어뷰징 방지의 1차 방어선은 dest_email별 제한이다(임의 주소로 스팸을 보내지 못하게 막는
# 핵심 장치). IP별 제한은 2차 백업일 뿐이라 기본값을 넉넉히 잡는다 — 강의실처럼 여러
# 학생이 같은 NAT(공유 IP)를 쓰는 환경에서 서로를 막지 않도록 하기 위함이다.
# 창(window)도 환경변수로 뺀다 - 운영자가 한도만 만지고 기간은 못 만지면 조절이 반쪽이다.
RATE_WINDOW = _int("RELAY_RATE_LIMIT_WINDOW_SECONDS", 3600)
# 기본값을 3에서 10으로 올린다. 3은 "정상적으로 쓰는 사람"이 먼저 걸리는 수였다: 기기를
# 옮기느라 두 번 보내고, 주소를 한 번 잘못 적고, 확인 코드 15분 TTL 을 넘겨 재요청하면
# 그것만으로 끝이다(실제로 개발 중 정상 사용만으로 소진됐다). 어뷰징의 실질적 상한은
# IP별 제한이고, 주소별 제한은 "한 사람에게 반복 발송"을 막는 장치라 이 정도면 충분하다.
RATE_PER_EMAIL = RateLimiter(limit=_int("RELAY_RATE_LIMIT_PER_EMAIL", 10), window_seconds=RATE_WINDOW)
RATE_PER_IP = RateLimiter(limit=_int("RELAY_RATE_LIMIT_PER_IP", 30), window_seconds=RATE_WINDOW)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8090").rstrip("/")


def _client_ip(request: Request) -> str:
    # Cloud Run 등 리버스 프록시 뒤에서는 request.client.host 가 항상 프록시 자신의 IP라
    # 전체 사용자가 하나의 rate-limit 키로 뭉쳐버린다. X-Forwarded-For 의 첫 값(원 클라이언트)을
    # 우선한다 — 이는 배포 환경의 엣지/프록시 계층이 이 헤더를 신뢰성 있게 설정해준다고
    # 가정하는 것이다(Cloud Run에서는 표준 동작). 프록시 없이 이 서비스가 직접 노출된다면
    # 호출자가 이 헤더를 스푸핑할 수 있으나, 이 경우 dest_email별 제한이 주 방어선이므로 허용한다.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@app.post("/sync/request", status_code=202)
def sync_request(body: SyncRequestBody, client_ip: str = Depends(_client_ip)) -> dict:
    try:
        RATE_PER_EMAIL.check(body.destination_email)
        RATE_PER_IP.check(client_ip)
    except RateLimitExceeded as e:
        raise HTTPException(
            status_code=429, detail=str(e), headers={"Retry-After": str(int(e.retry_after))}
        ) from e

    token, code = STORE.issue(body.destination_email, body.bundle)
    confirm_url = f"{PUBLIC_BASE_URL}/sync/confirm?token={token}"
    try:
        send_confirm_email(SMTP, body.destination_email, confirm_url)
    except MailSendError as e:
        STORE.consume(token)
        # 메일이 한 통도 나가지 않았다 - 사용자 몫을 깎지 않는다.
        RATE_PER_EMAIL.refund(body.destination_email)
        RATE_PER_IP.refund(client_ip)
        raise HTTPException(
            status_code=502, detail="확인 메일 발송에 실패했어요 - 잠시 후 다시 시도하세요"
        ) from e
    # 코드는 **메일에 넣지 않는다**. 메일함을 가진 사람이 아니라 요청을 시작한 사람만
    # 발송을 끝낼 수 있어야 하므로, 요청한 앱에만 돌려주고 앱이 자기 화면에 띄운다.
    # (수신 주소를 오타 냈을 때 낯선 사람이 링크를 눌러 번들을 받아가는 걸 막는 장치다.)
    return {"requested": True, "code": code}


_PAGE_STYLE = (
    "font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:520px;"
    "margin:56px auto;padding:0 20px;line-height:1.6;color:#1a1a1a"
)


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    """이 화면들은 비개발자가 메일 링크로 브라우저에서 직접 본다 - JSON 이 아니라 안내문이어야 한다."""
    return HTMLResponse(
        status_code=status,
        content=(
            f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{title}</title></head>"
            f'<body style="{_PAGE_STYLE}"><h1>{title}</h1>{body}</body></html>'
        ),
    )


def _expired_page() -> HTMLResponse:
    return _page(
        "요청이 만료됐어요",
        "<p>요청이 만료되었거나 이미 처리됐어요 - KeyLens에서 다시 내보내기를 시도하세요.</p>",
        status=410,
    )


def _code_form(token: str, error: str = "") -> HTMLResponse:
    note = f'<p style="color:#b3261e"><strong>{error}</strong></p>' if error else ""
    return _page(
        "확인 코드를 입력하세요",
        (
            "<p>KeyLens 앱 화면에 표시된 <strong>6자리 확인 코드</strong>를 입력하면 "
            "금고 파일을 보내드립니다.</p>"
            f"{note}"
            '<form method="post" action="/sync/confirm">'
            f'<input type="hidden" name="token" value="{html.escape(token)}">'
            '<input name="code" inputmode="numeric" autocomplete="one-time-code" '
            'pattern="[0-9]*" maxlength="6" required autofocus '
            'style="font-size:24px;letter-spacing:.3em;padding:10px 14px;width:200px">'
            '<button type="submit" style="font-size:16px;padding:11px 18px;margin-left:8px">'
            "보내기</button>"
            "</form>"
        ),
    )


@app.get("/sync/confirm", response_class=HTMLResponse)
def sync_confirm_form(token: str) -> HTMLResponse:
    """확인 코드 입력 폼만 보여준다 - **부작용이 없다.**

    예전에는 이 GET 이 곧바로 번들을 발송하고 토큰을 소진했다. 그런데 Gmail·Outlook ATP 같은
    메일 보안 스캐너는 메일 속 링크를 사용자 대신 미리 열어본다. 그러면 사용자가 누르지도
    않았는데 발송이 일어나고, 정작 눌렀을 때는 "만료됐다"는 화면을 보게 된다. 실제 발송은
    아래 POST 로 옮겼다 - 프리페치는 폼을 제출하지 않는다.
    """
    if STORE.peek(token) is None:
        return _expired_page()
    return _code_form(token)


@app.post("/sync/confirm", response_class=HTMLResponse)
async def sync_confirm_submit(request: Request) -> HTMLResponse:
    """코드가 맞으면 번들을 발송한다.

    폼 파싱을 직접 한다(fastapi 의 Form 이나 starlette 의 request.form 대신): 그 둘은
    python-multipart 를 요구하는데, HTML 폼의 기본 인코딩인 urlencoded 하나 읽자고
    런타임 의존성을 늘릴 이유가 없다(이 프로젝트는 certifi 때문에 httpx 도 뺐다).
    """
    fields = urllib.parse.parse_qs((await request.body()).decode("utf-8", errors="replace"))
    token = (fields.get("token") or [""])[0]
    code = (fields.get("code") or [""])[0].strip()

    entry = STORE.peek(token)
    if entry is None:
        return _expired_page()

    ok, attempts_left = STORE.verify_code(token, code)
    if not ok:
        if attempts_left <= 0:
            return _page(
                "확인에 실패했어요",
                "<p>코드를 여러 번 잘못 입력해 이 요청을 취소했어요 - "
                "KeyLens에서 다시 내보내기를 시도하세요.</p>",
                status=410,
            )
        return _code_form(
            token, f"코드가 맞지 않아요 - {attempts_left}번 더 시도할 수 있어요."
        )

    try:
        send_bundle_email(SMTP, entry.destination_email, json.dumps(entry.bundle))
    except MailSendError:
        # 토큰을 소진하지 않는다 - 발송만 실패한 것이라 같은 코드로 재시도할 수 있어야 한다.
        return _page(
            "발송에 실패했어요",
            "<p>파일 발송에 실패했어요 - 잠시 후 코드를 다시 입력해 주세요.</p>",
            status=502,
        )
    STORE.consume(token)
    return _page(
        "발송 완료",
        "<p>요청하신 파일을 이메일로 보냈습니다. 이메일함을 확인하세요.</p>",
    )


DEFAULT_PORT = 8090

if __name__ == "__main__":
    import uvicorn

    # Cloud Run(과 대부분의 PaaS)은 리스닝 포트를 PORT 환경변수로 주입한다 — 이를 무시하고
    # DEFAULT_PORT 로만 고정하면 배포 대상에서 기동에 실패한다.
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", DEFAULT_PORT)))
