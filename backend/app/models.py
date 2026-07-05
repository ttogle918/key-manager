# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Pydantic 스키마 — 지식베이스 정의와 API 입출력."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# ── 지식베이스 (knowledge/*.yaml) ──


class Credential(BaseModel):
    """서비스가 발급하는 자격증명 한 종류."""

    kind: str
    label: str
    label_patterns: list[str] = Field(default_factory=list)
    url_patterns: list[str] = Field(default_factory=list)
    value_regex: Optional[str] = None
    official_env_name: str
    expiry_known: bool = False


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
    password: str = Field(min_length=1, max_length=1024)


class VaultChangePassword(BaseModel):
    old_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=8, max_length=1024)


class VaultEntryCreate(BaseModel):
    """금고에 저장할 항목. value 는 암호화되어 저장되고 평문은 남지 않는다."""

    service: Optional[str] = None
    kind: Optional[str] = None
    official_name: Optional[str] = None
    value: str = Field(min_length=1, max_length=8192)
    label: Optional[str] = None
    expires_at: Optional[str] = None


class VaultEntryMeta(BaseModel):
    """항목 메타데이터(값 없음) — 잠금 상태에서도 노출 가능."""

    id: int
    service: Optional[str] = None
    kind: Optional[str] = None
    official_name: Optional[str] = None
    label: Optional[str] = None
    created_at: str
    expires_at: Optional[str] = None


class VaultValue(BaseModel):
    value: str
