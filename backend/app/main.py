# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 로컬 백엔드 API.

로컬 우선(local-first): 이 서버는 사용자 기기에서만 돌며 외부로 데이터를 보내지 않는다.
현재 제공: 지식베이스 조회 + Stage1 값 기반 분석. (암호화 저장·OCR·Stage2 는 후속.)
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import crypto
from .classify.pipeline import analyze
from .knowledge import load_knowledge_base
from .models import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
    VaultChangePassword,
    VaultEntryCreate,
    VaultEntryMeta,
    VaultEntryUpdate,
    VaultHistoryEntry,
    VaultInit,
    VaultPassword,
    VaultRotate,
    VaultStatus,
    VaultValue,
)
from .vault_session import VaultLocked, VaultRateLimited, VaultService

app = FastAPI(title="KeyLens API", version="0.1.0")

# 로컬 프론트엔드(Vite dev)만 허용.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5199",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5199",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# 지식베이스는 기동 시 1회 로드 (검증 실패하면 서버가 뜨지 않는다).
KB = load_knowledge_base()

# 금고 파일 위치(로컬 전용). 기본은 backend/vault.db(.gitignore 로 제외). 환경변수로 재정의 가능.
_VAULT_PATH = os.environ.get(
    "KEYLENS_VAULT_PATH", str(Path(__file__).resolve().parent.parent / "vault.db")
)
# 잠금 정책(자동잠금·실패지연)은 KEYLENS_* 환경변수로 조정 가능(.env.example 참고).
VAULT = VaultService.from_env(_VAULT_PATH)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok", services=len(KB.services), credentials=KB.credential_count
    )


@app.get("/knowledge")
def knowledge() -> dict:
    """프론트가 종류·변수명 맵을 동적으로 구성할 수 있도록 지식베이스를 노출."""
    return {
        "services": [
            {
                "service": s.service,
                "display_name": s.display_name,
                "credentials": [
                    {
                        "kind": c.kind,
                        "label": c.label,
                        "official_env_name": c.official_env_name,
                        "value_based": c.value_regex is not None,
                        "expiry_known": c.expiry_known,
                    }
                    for c in s.credentials
                ],
            }
            for s in KB.services
        ]
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    return analyze(request, KB)


# ── 금고 (VAULT-1/2) ─────────────────────────────────────────────
# 값은 잠금 해제(인증) 상태에서만 복호화된다. 잠금 상태에선 메타데이터만 노출.


@app.get("/vault/status", response_model=VaultStatus)
def vault_status() -> VaultStatus:
    return VaultStatus(**VAULT.status())


@app.post("/vault/init", response_model=VaultStatus)
def vault_init(body: VaultInit) -> VaultStatus:
    if VAULT.is_initialized():
        raise HTTPException(status_code=409, detail="이미 금고가 있습니다 — 잠금 해제하세요")
    VAULT.init(body.password)
    return VaultStatus(**VAULT.status())


@app.post("/vault/unlock", response_model=VaultStatus)
def vault_unlock(body: VaultPassword) -> VaultStatus:
    try:
        VAULT.unlock(body.password)
    except VaultRateLimited as e:
        raise HTTPException(
            status_code=429, detail=str(e), headers={"Retry-After": str(e.retry_after)}
        ) from e
    except crypto.DecryptError:
        raise HTTPException(status_code=401, detail="마스터 비밀번호가 올바르지 않습니다") from None
    except ValueError as e:  # 초기화되지 않은 금고
        raise HTTPException(status_code=409, detail=str(e)) from e
    return VaultStatus(**VAULT.status())


@app.post("/vault/lock", response_model=VaultStatus)
def vault_lock() -> VaultStatus:
    VAULT.lock()
    return VaultStatus(**VAULT.status())


@app.get("/vault/entries", response_model=list[VaultEntryMeta])
def vault_list() -> list[VaultEntryMeta]:
    return [VaultEntryMeta(**m) for m in VAULT.list_entries()]


@app.post("/vault/entries", response_model=VaultEntryMeta)
def vault_add(body: VaultEntryCreate) -> VaultEntryMeta:
    try:
        eid = VAULT.add_entry(
            service=body.service, kind=body.kind, official_name=body.official_name,
            value=body.value, label=body.label, project=body.project, memo=body.memo,
            expires_at=body.expires_at,
        )
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    return next(m for m in [VaultEntryMeta(**x) for x in VAULT.list_entries()] if m.id == eid)


@app.patch("/vault/entries/{entry_id}", response_model=VaultEntryMeta)
def vault_update(entry_id: int, body: VaultEntryUpdate) -> VaultEntryMeta:
    try:
        ok = VAULT.update_meta(
            entry_id, project=body.project, memo=body.memo, expires_at=body.expires_at
        )
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    if not ok:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다")
    return next(m for m in [VaultEntryMeta(**x) for x in VAULT.list_entries()] if m.id == entry_id)


@app.post("/vault/entries/{entry_id}/rotate", response_model=VaultEntryMeta)
def vault_rotate(entry_id: int, body: VaultRotate) -> VaultEntryMeta:
    try:
        ok = VAULT.rotate(entry_id, body.value)
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    if not ok:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다")
    return next(m for m in [VaultEntryMeta(**x) for x in VAULT.list_entries()] if m.id == entry_id)


@app.delete("/vault/entries/{entry_id}", response_model=VaultStatus)
def vault_delete(entry_id: int) -> VaultStatus:
    try:
        ok = VAULT.delete_entry(entry_id)
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    if not ok:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다")
    return VaultStatus(**VAULT.status())


_ACCESS_EVENTS = {"reveal", "copy", "export"}


@app.get("/vault/entries/{entry_id}/value", response_model=VaultValue)
def vault_get_value(entry_id: int, event: str = "reveal") -> VaultValue:
    if event not in _ACCESS_EVENTS:
        event = "reveal"  # 알 수 없는 이벤트는 열람으로 기록
    try:
        return VaultValue(value=VAULT.get_value(entry_id, event))
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    except KeyError:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다") from None
    except crypto.DecryptError:
        raise HTTPException(status_code=422, detail="복호화 실패 — 데이터 무결성 오류") from None


@app.get("/vault/entries/{entry_id}/history", response_model=list[VaultHistoryEntry])
def vault_history(entry_id: int) -> list[VaultHistoryEntry]:
    try:
        return [VaultHistoryEntry(**h) for h in VAULT.history(entry_id)]
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None


@app.post("/vault/change-password", response_model=VaultStatus)
def vault_change_password(body: VaultChangePassword) -> VaultStatus:
    try:
        VAULT.change_password(body.old_password, body.new_password)
    except crypto.DecryptError:
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다") from None
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return VaultStatus(**VAULT.status())


# 로컬 기본 포트 8003 (흔한 8000 회피). `python -m app.main` 으로 실행 가능.
DEFAULT_PORT = 8003

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=DEFAULT_PORT)
