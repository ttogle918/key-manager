# SPDX-FileCopyrightText: 2026 ttogle918
# SPDX-License-Identifier: MIT
"""엔드포인트 입출력 스키마."""
from __future__ import annotations

import re

from pydantic import BaseModel, field_validator

# pydantic[email]의 EmailStr는 email-validator 신규 의존성을 끌어오므로 정규식으로 직접 검증한다.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SyncRequestBody(BaseModel):
    destination_email: str
    bundle: dict

    @field_validator("destination_email")
    @classmethod
    def _validate_email(cls, v: str) -> str:
        if not _EMAIL_RE.match(v):
            raise ValueError("올바른 이메일 형식이 아니에요")
        return v
