# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""엔드포인트 입출력 스키마."""
from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

# pydantic[email]의 EmailStr는 email-validator 신규 의존성을 끌어오므로 정규식으로 직접 검증한다.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# SYNC-0 export_bundle()이 실제로 쓰는 형식 문자열(backend/app/vault_repo.py BUNDLE_FORMAT).
# 이 값이 아니면 KeyLens 번들이 아니라고 보고 거부한다 — 이 엔드포인트는 인증이 없는 공개
# API라, 형식 검증 없이 받으면 공격자가 임의 내용을 매니저의 평판 좋은 메일 주소로 아무
# 수신자에게나 발송시키는 데 악용할 수 있다.
BUNDLE_FORMAT = "keylens-vault"


class SyncRequestBody(BaseModel):
    destination_email: str
    bundle: dict

    @field_validator("destination_email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        # $ 는 트레일링 개행 앞에서도 매치되어 "a@b.c\n" 같은 값을 통과시킬 수 있다 —
        # fullmatch 로 문자열 전체를 강제한다.
        if not _EMAIL_RE.fullmatch(v):
            raise ValueError("올바른 이메일 형식이 아니에요")
        return v

    @field_validator("bundle")
    @classmethod
    def _validate_bundle(cls, v: dict) -> dict:
        if v.get("format") != BUNDLE_FORMAT:
            raise ValueError("올바른 금고 번들 형식이 아니에요")
        return v
