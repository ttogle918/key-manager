# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Pydantic 스키마 — 지식베이스 정의와 API 입출력."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ── 지식베이스 (knowledge/*.yaml) ──


class VerifySpec(BaseModel):
    """키 유효성 검증용 read-only 호출 정의 (TRUST-1).

    서비스가 제공하는 '조회만 하는' 엔드포인트를 지식베이스에 선언해 두고,
    사용자가 명시적으로 요청할 때 1회 호출해 키가 살아있는지 확인한다.
    부수효과가 없는(read-only) GET/HEAD 만 허용한다.
    """

    method: Literal["GET", "HEAD"] = "GET"
    url: str
    # 키를 요청에 싣는 방식: Authorization: Bearer <키> / 커스텀 헤더 / 쿼리 파라미터.
    auth: Literal["bearer", "header", "query"] = "bearer"
    header_name: Optional[str] = None  # auth=header 일 때 헤더 이름(예: Authorization)
    prefix: str = ""  # auth=header 값 접두어(예: "KakaoAK ")
    query_name: Optional[str] = None  # auth=query 일 때 파라미터 이름
    extra_headers: dict[str, str] = Field(default_factory=dict)  # 예: Notion-Version


class Credential(BaseModel):
    """서비스가 발급하는 자격증명 한 종류."""

    kind: str
    label: str
    label_patterns: list[str] = Field(default_factory=list)
    url_patterns: list[str] = Field(default_factory=list)
    value_regex: Optional[str] = None
    official_env_name: str
    expiry_known: bool = False
    verify: Optional[VerifySpec] = None


class Service(BaseModel):
    """지식베이스의 서비스 하나."""

    service: str
    display_name: str
    credentials: list[Credential]


# ── API 입출력 ──


class AnalyzeRequest(BaseModel):
    """분석 요청. 최소 하나의 소스를 담는다.

    로컬 전용 API지만 폭주 입력(거대 텍스트 → 정규식 부하)은 상한으로 차단한다.
    """

    text: Optional[str] = Field(default=None, max_length=100_000)
    url: Optional[str] = Field(default=None, max_length=4096)


Confidence = Literal["high", "medium", "low", "unknown"]


class ConflictOption(BaseModel):
    """신호 충돌 시 사용자가 고르는 후보 한 개 (Stage2)."""

    kind: str
    label: str
    official_env_name: str
    evidence: str
    signal: str
    strong: bool


class ClassifiedItem(BaseModel):
    """분류된 자격증명 후보 한 건."""

    value: str
    masked: str
    service: Optional[str] = None
    display_name: Optional[str] = None
    kind: str
    label: str
    official_env_name: Optional[str] = None
    confidence: Confidence
    format: str
    source: str
    stage: int
    conflict: bool = False
    options: list[ConflictOption] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    items: list[ClassifiedItem]
    count: int


class HealthResponse(BaseModel):
    status: str
    services: int
    credentials: int


# ── 금고 (VAULT-1/2) ──


class VaultStatus(BaseModel):
    initialized: bool
    unlocked: bool


class VaultPassword(BaseModel):
    # 잠금 해제용 — 입력 비밀번호는 길이를 강제하지 않는다(이미 만든 금고를 여는 것).
    password: str = Field(min_length=1, max_length=1024)


class VaultInit(BaseModel):
    """새 금고 생성 — 마스터 비밀번호 최소 길이를 백엔드에서도 강제(방어 심화)."""

    password: str = Field(min_length=8, max_length=1024)


class VaultChangePassword(BaseModel):
    old_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class VaultEntryCreate(BaseModel):
    """금고에 저장할 항목. value 는 암호화되어 저장되고 평문은 남지 않는다(project/memo 는 평문 메타)."""

    service: Optional[str] = None
    kind: Optional[str] = None
    official_name: Optional[str] = None
    value: str = Field(min_length=1, max_length=8192)
    label: Optional[str] = None
    project: Optional[str] = None
    memo: Optional[str] = None
    expires_at: Optional[str] = None


class VaultEntryUpdate(BaseModel):
    """평문 메타데이터만 수정(값·암호문은 불변)."""

    project: Optional[str] = None
    memo: Optional[str] = None
    expires_at: Optional[str] = None


class VaultEntryMeta(BaseModel):
    """항목 메타데이터(값 없음) — 잠금 상태에서도 노출 가능."""

    id: int
    service: Optional[str] = None
    kind: Optional[str] = None
    official_name: Optional[str] = None
    label: Optional[str] = None
    project: Optional[str] = None
    memo: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None


class VaultValue(BaseModel):
    value: str


class VaultRotate(BaseModel):
    """값 교체 요청 — 새 값으로 재암호화(옛 값 폐기)."""

    value: str = Field(min_length=1, max_length=8192)


class VaultHistoryEntry(BaseModel):
    """감사 이력 한 줄(값 없음) — 등록·열람·복사·내보내기."""

    date: str
    event: str


VerifyStatus = Literal["active", "invalid", "unknown", "unsupported"]


class VaultVerifyResult(BaseModel):
    """키 유효성 검증 결과(값 없음) — 상태만 노출(TRUST-1).

    - active: 서비스가 키를 인정(2xx)
    - invalid: 인증 거부(401/403) — 폐기·오타 키
    - unknown: 판단 불가(네트워크 오류·타임아웃·429 등)
    - unsupported: 지식베이스에 검증 엔드포인트가 없는 서비스
    """

    status: VerifyStatus
    detail: str
