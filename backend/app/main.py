# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""KeyLens 로컬 백엔드 API.

로컬 우선(local-first): 이 서버는 사용자 기기에서만 돌며 외부로 데이터를 보내지 않는다.
현재 제공: 지식베이스 조회 + Stage1 값 기반 분석. (암호화 저장·OCR·Stage2 는 후속.)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from . import crypto, desktop, discoveries_repo, explain, ollama_client
from .classify.pipeline import analyze
from .knowledge import load_knowledge_base
from .models import (
    SdkDirEntry,
    DesktopCapabilities,
    PickedDirectory,
    AnalyzeRequest,
    AnalyzeResponse,
    ExplainDiscoveryApprove,
    ExplainImageResponse,
    ExplainStatusResponse,
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
from .ocr import OcrUnavailableError, run_ocr
from .ollama_client import OllamaConfig
from .tavily_client import TavilyConfig
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


_MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15MB — 스크린샷 한 장 기준 넉넉히, 폭주 입력은 차단


@app.post("/analyze/image", response_model=AnalyzeResponse)
async def analyze_image_endpoint(
    image: UploadFile = File(...),
    url: str | None = Form(default=None),
    text: str | None = Form(default=None),
) -> AnalyzeResponse:
    """스크린샷 이미지를 로컬 OCR(RapidOCR, 한국어 인식 모델)로 읽어 기존 분류 파이프라인에 먹인다.

    이미지는 이 로컬 백엔드(127.0.0.1) 안에서만 처리되고 디스크에 저장되지 않는다.
    `text`(사용자가 직접 붙여넣은 텍스트, 선택)가 있으면 OCR 결과 뒤에 이어붙여 함께 분석한다.
    """
    if image.content_type is None or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="이미지 파일만 업로드할 수 있어요")

    data = await image.read(_MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="빈 파일이에요")
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="이미지가 너무 커요(15MB 제한)")

    try:
        ocr_text = run_ocr(data)
    except OcrUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    except Exception:
        raise HTTPException(
            status_code=422, detail="이미지를 읽지 못했어요 — 다른 스크린샷으로 시도해 주세요"
        ) from None

    combined_text = "\n".join(t for t in (ocr_text, text) if t)
    return analyze(AnalyzeRequest(text=combined_text, url=url), KB)


# ── 화면 설명(EXPLAIN, 1단계) ──
# 로컬 Ollama가 없거나 OLLAMA_MODEL이 설정 안 됐으면 기능 자체가 비활성(None) — 앱은 어떤
# 모델도 번들하지 않는다. 설계 근거: docs/superpowers/specs/2026-08-27-screenshot-explain-design.md

OLLAMA_CONFIG = OllamaConfig.from_env()
TAVILY_CONFIG = TavilyConfig.from_env()
DISCOVERIES_PATH = os.environ.get(
    "KEYLENS_LOCAL_DISCOVERIES_PATH",
    str(Path(__file__).resolve().parent.parent / "local_discoveries.yaml"),
)


@app.get("/explain/status", response_model=ExplainStatusResponse)
def explain_status() -> ExplainStatusResponse:
    available = OLLAMA_CONFIG is not None and ollama_client.is_available(OLLAMA_CONFIG)
    return ExplainStatusResponse(available=available)


@app.post("/explain/image", response_model=ExplainImageResponse)
async def explain_image_endpoint(image: UploadFile = File(...)) -> ExplainImageResponse:
    if OLLAMA_CONFIG is None:
        raise HTTPException(
            status_code=503,
            detail="화면 설명 기능이 설정되지 않았어요 — OLLAMA_MODEL 환경변수를 설정하세요",
        )
    if image.content_type is None or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="이미지 파일만 업로드할 수 있어요")

    data = await image.read(_MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="빈 파일이에요")
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="이미지가 너무 커요(15MB 제한)")

    try:
        # RapidOCR 추론 + Ollama HTTP 호출(최대 30s)은 동기 블로킹이라 이벤트 루프에서
        # 직접 돌리면 그 사이 다른 요청(RUNTIME-1 SDK 큐 포함)이 전부 멈춘다 — 스레드풀로 위임.
        boxes = await run_in_threadpool(
            explain.explain_image, data, KB, OLLAMA_CONFIG, TAVILY_CONFIG, DISCOVERIES_PATH
        )
    except OcrUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    except ollama_client.OllamaUnavailableError:
        raise HTTPException(
            status_code=503,
            detail="로컬 LLM에 연결할 수 없어요 — Ollama가 실행 중인지 확인하세요",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=422, detail="이미지를 읽지 못했어요 — 다른 스크린샷으로 시도해 주세요"
        ) from None
    return ExplainImageResponse(boxes=boxes)


@app.post("/explain/discoveries", status_code=204)
async def explain_discoveries_endpoint(body: ExplainDiscoveryApprove) -> None:
    """사용자가 화면에서 승인한 AI 추정 1건을 로컬 발견 캐시에 저장(설계 판단 D)."""
    if body.tier == "known":
        raise HTTPException(status_code=422, detail="known 등급은 저장 대상이 아니에요")
    if body.label == explain.UNKNOWN_LABEL:
        # 프론트가 "알 수 없음" 라벨엔 저장 버튼 자체를 안 보여주지만(방어 심화), 여기서도 막는다 —
        # 한 번 캐시되면 재검증 없이 계속 재사용되므로("확인 실패" 패턴이 영구 고정됨) 방지 가치가 큼.
        raise HTTPException(status_code=422, detail="확인되지 않은 추정은 저장 대상이 아니에요")
    pattern = discoveries_repo.normalize_pattern(body.text)
    await run_in_threadpool(
        discoveries_repo.append_discovery,
        DISCOVERIES_PATH,
        pattern=pattern, label=body.label, tier=body.tier, docs_url=body.docs_url,
    )


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


def _today() -> str:
    """프로젝트 미지정 저장의 기본값(UTC) — keylens-env 컬렉션명으로도 그대로 쓰일 수 있다."""
    return datetime.now(timezone.utc).date().isoformat()


@app.get("/vault/entries", response_model=list[VaultEntryMeta])
def vault_list() -> list[VaultEntryMeta]:
    return [VaultEntryMeta(**m) for m in VAULT.list_entries()]


@app.post("/vault/entries", response_model=VaultEntryMeta)
def vault_add(body: VaultEntryCreate) -> VaultEntryMeta:
    project = (body.project or "").strip() or _today()
    try:
        eid = VAULT.add_entry(
            service=body.service, kind=body.kind, official_name=body.official_name,
            value=body.value, label=body.label, project=project, memo=body.memo,
            expires_at=body.expires_at,
        )
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    return next(m for m in [VaultEntryMeta(**x) for x in VAULT.list_entries()] if m.id == eid)


@app.patch("/vault/entries/{entry_id}", response_model=VaultEntryMeta)
def vault_update(entry_id: int, body: VaultEntryUpdate) -> VaultEntryMeta:
    sent = body.model_fields_set  # 생략한 필드는 건드리지 않는다
    fields: dict[str, str | None] = {}

    if "project" in sent:
        project = (body.project or "").strip()
        if not project:
            # project를 비우면 "오늘"이 아니라 그 항목의 등록일로 되돌린다 — 수정 행위 자체가
            # 그룹핑 날짜를 오늘로 밀어버리면 안 되므로.
            current = next((m for m in VAULT.list_entries() if m["id"] == entry_id), None)
            project = current["created_at"][:10] if current else _today()
        fields["project"] = project
    if "memo" in sent:
        fields["memo"] = body.memo
    if "expires_at" in sent:
        fields["expires_at"] = body.expires_at

    # 서비스 재지정(RUNTIME-4). service·kind 는 한 묶음으로만 바뀐다 — 한쪽만 바꾸면
    # 지식베이스에 없는 조합이 되어 유효성 검증이 unsupported 로 죽는다.
    if "service" in sent or "kind" in sent:
        if ("service" in sent) != ("kind" in sent):
            raise HTTPException(
                status_code=422, detail="service 와 kind 는 함께 보내야 합니다"
            )
        if bool(body.service) != bool(body.kind):
            raise HTTPException(
                status_code=422, detail="service 와 kind 는 함께 지정하거나 함께 비워야 합니다"
            )
        if body.service:
            cred = KB.find(body.service, body.kind or "")
            if cred is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"지식베이스에 없는 조합입니다: {body.service}/{body.kind}",
                )
            # 라벨은 지식베이스가 정한다 — 클라이언트가 보낸 값을 그대로 믿지 않는다.
            fields["service"], fields["kind"], fields["label"] = (
                body.service,
                body.kind,
                cred.label,
            )
        else:
            # 미지정으로 되돌리기
            fields["service"] = fields["kind"] = fields["label"] = None

    if not fields:
        raise HTTPException(status_code=422, detail="수정할 필드가 없습니다")

    try:
        ok = VAULT.update_meta(entry_id, **fields)
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


@app.post("/vault/reset", response_model=VaultStatus)
def vault_reset(body: VaultPassword) -> VaultStatus:
    """금고 완전 초기화(VAULT-RESET) — 교육·공용 PC용. 비밀번호 재확인 필수, 되돌릴 수 없음."""
    try:
        VAULT.reset(body.password)
    except crypto.DecryptError:
        raise HTTPException(status_code=401, detail="마스터 비밀번호가 올바르지 않습니다") from None
    except ValueError as e:  # 초기화되지 않은 금고
        raise HTTPException(status_code=409, detail=str(e)) from e
    return VaultStatus(**VAULT.status())


# ── RUNTIME-1: SDK 접근 관리 ──
# keylens-env SDK가 프로젝트별로 어떤 디렉토리에서 값을 가져갈 수 있는지 관리한다.
# /sdk/env 는 실제 값을 반환하므로 인증(잠금 해제) 필수.
# 관리 엔드포인트는 다루는 데이터(문자열)가 아니라 **권한 방향**으로 나눈다:
#   - 권한을 넓히는 쪽(디렉토리 등록·대기 요청 승인) → 잠금 해제 필수.
#     열어 두면 아무 로컬 프로세스나 자기 경로를 스스로 승인해 승인 화면을 무력화한다.
#   - 권한을 좁히는 쪽(등록 해제·거부)과 단순 조회 → 잠금 상태에서도 허용(안전한 방향).


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
    try:
        return SdkProjectDir(**VAULT.add_project_dir(project, body.path))
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None


@app.delete("/sdk/projects/{project}/directories/{dir_id}")
def sdk_remove_dir(project: str, dir_id: int) -> dict:
    ok = VAULT.remove_project_dir(project, dir_id)
    if not ok:
        raise HTTPException(status_code=404, detail="디렉토리를 찾을 수 없습니다")
    return {"removed": True}


@app.get("/sdk/directories", response_model=list[SdkDirEntry])
def sdk_list_all_dirs() -> list[SdkDirEntry]:
    """모든 컬렉션의 허용 디렉토리. "내가 뭘 허용해 뒀지"에 한 번에 답한다."""
    return [SdkDirEntry(**d) for d in VAULT.list_all_project_dirs()]


@app.get("/desktop/capabilities", response_model=DesktopCapabilities)
def desktop_capabilities() -> DesktopCapabilities:
    """데스크톱 셸에서만 되는 기능을 프론트에 알려준다(브라우저면 전부 false)."""
    return DesktopCapabilities(directory_picker=desktop.has_directory_picker())


@app.post("/desktop/pick-directory", response_model=PickedDirectory)
async def desktop_pick_directory() -> PickedDirectory:
    """네이티브 폴더 선택창을 띄우고 고른 절대경로를 돌려준다.

    금고가 잠겨 있으면 거절한다. 고른 경로로 할 수 있는 일(디렉토리 등록)이 어차피 잠금
    해제를 요구하므로, 잠긴 상태에서 대화상자만 뜨는 건 쓸모도 없고 표면만 넓힌다.

    대화상자는 사용자가 닫을 때까지 반환하지 않는다 - 이벤트 루프를 붙잡지 않도록
    스레드풀로 넘긴다(그러지 않으면 대화상자가 떠 있는 동안 앱 전체가 멈춘 것처럼 보인다).
    """
    if not VAULT.status()["unlocked"]:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 - 인증하세요")
    try:
        path = await run_in_threadpool(desktop.pick_directory)
    except desktop.DirectoryPickerUnavailable as e:
        raise HTTPException(status_code=501, detail=str(e)) from None
    return PickedDirectory(path=path)


@app.get("/sdk/pending", response_model=list[SdkPendingRequest])
def sdk_list_pending() -> list[SdkPendingRequest]:
    return [SdkPendingRequest(**p) for p in VAULT.list_pending()]


@app.post("/sdk/pending/{pending_id}/approve")
def sdk_approve_pending(pending_id: int) -> dict:
    try:
        ok = VAULT.approve_pending(pending_id)
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
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
