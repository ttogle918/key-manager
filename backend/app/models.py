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
    """분석 요청. 최소 하나의 소스를 담는다."""

    text: Optional[str] = None
    url: Optional[str] = None


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
