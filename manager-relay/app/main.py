# SPDX-FileCopyrightText: 2026 ttogle918
# SPDX-License-Identifier: MIT
"""KeyLens 매니저 릴레이 API.

계정·DB 없이 SMTP로만 암호화 금고 번들을 목적지 이메일로 전달한다. 이 서버는
평문을 절대 보지 않고(번들은 이미 암호문), 요청 처리가 끝나면 아무것도 영구 저장하지
않는다(docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md).
"""
from __future__ import annotations

import json
import os

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .mailer import MailSendError, SmtpConfig, send_bundle_email, send_confirm_email
from .models import SyncRequestBody
from .rate_limit import RateLimitExceeded, RateLimiter
from .token_store import TokenStore

app = FastAPI(title="KeyLens Manager Relay", version="0.1.0")

# 이 릴레이는 자격증명을 쓰지 않는 공개 API라, 배포되는 exe가 어떤 로컬 오리진에서
# 오든(사용자마다 포트가 다를 수 있음) 그대로 허용한다. 쿠키/세션이 없어 안전하다.
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
RATE_PER_EMAIL = RateLimiter(limit=_int("RELAY_RATE_LIMIT_PER_EMAIL", 3))
RATE_PER_IP = RateLimiter(limit=_int("RELAY_RATE_LIMIT_PER_IP", 10))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/")


def _client_ip(request: Request) -> str:
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

    token = STORE.issue(body.destination_email, body.bundle)
    confirm_url = f"{PUBLIC_BASE_URL}/sync/confirm?token={token}"
    try:
        send_confirm_email(SMTP, body.destination_email, confirm_url)
    except MailSendError as e:
        STORE.consume(token)
        raise HTTPException(
            status_code=502, detail="확인 메일 발송에 실패했어요 — 잠시 후 다시 시도하세요"
        ) from e
    return {"requested": True}


@app.get("/sync/confirm", response_class=HTMLResponse)
def sync_confirm(token: str) -> str:
    entry = STORE.peek(token)
    if entry is None:
        raise HTTPException(
            status_code=410,
            detail="요청이 만료되었거나 이미 처리됐어요 — KeyLens에서 다시 내보내기를 시도하세요",
        )
    try:
        send_bundle_email(SMTP, entry.destination_email, json.dumps(entry.bundle))
    except MailSendError as e:
        raise HTTPException(
            status_code=502, detail="파일 발송에 실패했어요 — 이 링크를 다시 눌러 재시도하세요"
        ) from e
    STORE.consume(token)
    return (
        "<html><body><h1>발송 완료</h1>"
        "<p>요청하신 파일을 이메일로 보냈습니다. 이메일함을 확인하세요.</p></body></html>"
    )


DEFAULT_PORT = 8090

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=DEFAULT_PORT)
