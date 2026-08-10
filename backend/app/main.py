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
    SdkAddDirRequest,
    SdkEnvRequest,
    SdkEnvResponse,
    SdkPendingRequest,
    SdkProject,
    SdkProjectDir,
    VaultChangePassword,
    VaultEntryCreate,
    VaultEntryMeta,
    VaultEntryUpdate,
    VaultHistoryEntry,
    VaultImportRequest,
    VaultImportResult,
    VaultInit,
    VaultPassword,
    VaultRotate,
    VaultStatus,
    VaultValue,
    VaultVerifyResult,
)
from .vault_session import SdkApprovalPending, VaultLocked, VaultRateLimited, VaultService

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
    # 프론트가 실제로 쓰는 메서드 전부 — dev 모드는 교차 오리진이라 DELETE·PATCH 도
    # 프리플라이트를 타므로 여기서 빠지면 항목 삭제·메모 수정·디렉토리 해제가 실패한다.
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
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
                # 발급 도움말 서비스 단위 (GUIDE-1) + 종류 구분법 (GUIDE-2)
                "console_url": s.console_url,
                "steps": s.steps,
                "prereq": s.prereq,
                "disambiguation": s.disambiguation,
                "credentials": [
                    {
                        "kind": c.kind,
                        "label": c.label,
                        "official_env_name": c.official_env_name,
                        "value_based": c.value_regex is not None,
                        "expiry_known": c.expiry_known,
                        "verifiable": c.verify is not None,
                        # 발급 도움말 종류 단위 (GUIDE-1) — 값 없음, 안내 메타만
                        "role": c.role,
                        "issue_url": c.issue_url,
                        "docs_url": c.docs_url,
                        # 보안 등급·유출 대응 (GUIDE-2)
                        "exposure": c.exposure,
                        "impact": c.impact,
                        "security_tip": c.security_tip,
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
    try:
        crypto.check_password_strength(body.password)
    except crypto.WeakPasswordError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
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


@app.post("/vault/entries/{entry_id}/verify", response_model=VaultVerifyResult)
def vault_verify(entry_id: int) -> VaultVerifyResult:
    """항목의 키를 서비스로 1회 검증 호출 → active/invalid/unknown(값 비노출).

    지식베이스에 검증 엔드포인트가 없는 서비스는 unsupported 로 응답(호출 자체 안 함).
    명시적 사용자 요청(POST)일 때만 실행된다 — 자동 주기 호출 없음.
    """
    meta = next((m for m in VAULT.list_entries() if m["id"] == entry_id), None)
    if meta is None:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다")

    cred = (
        KB.find(meta["service"], meta["kind"])
        if meta.get("service") and meta.get("kind")
        else None
    )
    if cred is None or cred.verify is None:
        return VaultVerifyResult(
            status="unsupported", detail="이 서비스는 아직 유효성 검증을 지원하지 않습니다"
        )

    try:
        status, detail = VAULT.verify_entry(entry_id, cred.verify)
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    except KeyError:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다") from None
    except crypto.DecryptError:
        raise HTTPException(status_code=422, detail="복호화 실패 — 데이터 무결성 오류") from None
    return VaultVerifyResult(status=status, detail=detail)


@app.get("/vault/entries/{entry_id}/history", response_model=list[VaultHistoryEntry])
def vault_history(entry_id: int) -> list[VaultHistoryEntry]:
    try:
        return [VaultHistoryEntry(**h) for h in VAULT.history(entry_id)]
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None


@app.post("/vault/export")
def vault_export() -> dict:
    """암호화 금고 번들 내보내기(인증 상태에서만) — 전부 암호문. 마스터 비밀번호 없이는 못 연다."""
    try:
        return VAULT.export_bundle()
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    except ValueError as e:  # 초기화되지 않은 금고
        raise HTTPException(status_code=409, detail=str(e)) from e


@app.post("/vault/import", response_model=VaultImportResult)
def vault_import(body: VaultImportRequest) -> VaultImportResult:
    """금고 번들 가져오기 — 마스터 비밀번호로 복호화 성공 시에만 교체/병합.

    비밀번호가 틀리거나 파일이 손상되면 기존 금고는 무손상으로 남는다.
    """
    try:
        result = VAULT.import_bundle(body.bundle, body.password, body.mode)
    except crypto.DecryptError:
        raise HTTPException(status_code=401, detail="마스터 비밀번호가 올바르지 않습니다") from None
    except VaultLocked:
        raise HTTPException(
            status_code=401, detail="병합하려면 먼저 현재 금고를 잠금 해제하세요"
        ) from None
    except ValueError as e:  # 형식·버전·손상
        raise HTTPException(status_code=422, detail=str(e)) from e
    return VaultImportResult(**result)


@app.post("/vault/change-password", response_model=VaultStatus)
def vault_change_password(body: VaultChangePassword) -> VaultStatus:
    try:
        crypto.check_password_strength(body.new_password)
    except crypto.WeakPasswordError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    try:
        VAULT.change_password(body.old_password, body.new_password)
    except crypto.DecryptError:
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다") from None
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return VaultStatus(**VAULT.status())


# ── RUNTIME-1: SDK 접근 관리 ──
# keylens-env SDK가 프로젝트별로 어떤 디렉토리에서 값을 가져갈 수 있는지 관리한다.
# /sdk/env 는 실제 값을 반환하므로 인증(잠금 해제) 필수 — 그 외 관리 엔드포인트는
# 프로젝트명·경로 문자열(비밀 아님)만 다루므로 잠금 상태에서도 접근을 막지 않는다.


@app.post("/sdk/env", response_model=SdkEnvResponse)
def sdk_env(body: SdkEnvRequest) -> SdkEnvResponse:
    try:
        values = VAULT.sdk_env(body.project, body.path)
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    except SdkApprovalPending as e:
        raise HTTPException(status_code=403, detail=str(e)) from None
    except crypto.DecryptError:
        raise HTTPException(status_code=422, detail="복호화 실패 — 데이터 무결성 오류") from None
    return SdkEnvResponse(values=values)


@app.get("/sdk/projects", response_model=list[SdkProject])
def sdk_list_projects() -> list[SdkProject]:
    return [SdkProject(**p) for p in VAULT.list_projects()]


@app.get("/sdk/projects/{project}/directories", response_model=list[SdkProjectDir])
def sdk_list_dirs(project: str) -> list[SdkProjectDir]:
    return [SdkProjectDir(**d) for d in VAULT.list_project_dirs(project)]


@app.post("/sdk/projects/{project}/directories", response_model=SdkProjectDir)
def sdk_add_dir(project: str, body: SdkAddDirRequest) -> SdkProjectDir:
    return SdkProjectDir(**VAULT.add_project_dir(project, body.path))


@app.delete("/sdk/projects/{project}/directories/{dir_id}")
def sdk_remove_dir(project: str, dir_id: int) -> dict:
    ok = VAULT.remove_project_dir(project, dir_id)
    if not ok:
        raise HTTPException(status_code=404, detail="디렉토리를 찾을 수 없습니다")
    return {"removed": True}


@app.get("/sdk/pending", response_model=list[SdkPendingRequest])
def sdk_list_pending() -> list[SdkPendingRequest]:
    return [SdkPendingRequest(**p) for p in VAULT.list_pending()]


@app.post("/sdk/pending/{pending_id}/approve")
def sdk_approve_pending(pending_id: int) -> dict:
    ok = VAULT.approve_pending(pending_id)
    if not ok:
        raise HTTPException(status_code=404, detail="대기 중인 요청을 찾을 수 없습니다")
    return {"approved": True}


@app.post("/sdk/pending/{pending_id}/deny")
def sdk_deny_pending(pending_id: int) -> dict:
    ok = VAULT.deny_pending(pending_id)
    if not ok:
        raise HTTPException(status_code=404, detail="대기 중인 요청을 찾을 수 없습니다")
    return {"denied": True}


# 로컬 기본 포트 8003 (흔한 8000 회피). `python -m app.main` 으로 실행 가능.
DEFAULT_PORT = 8003

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=DEFAULT_PORT)
