# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""지식베이스 로더 — knowledge/*.yaml 을 읽어 검증하고 컴파일한다."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import Credential, Service

# knowledge/ 디렉토리 기본 위치 (backend/knowledge).
# 패키징된 실행 파일(데스크톱 앱)은 번들 위치가 달라, KEYLENS_KNOWLEDGE_DIR 로 재정의할 수 있게 한다.
DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


@dataclass
class ValueMatcher:
    """value_regex 를 가진 자격증명과 컴파일된 정규식."""

    service: Service
    credential: Credential
    pattern: re.Pattern[str]


@dataclass
class KnowledgeBase:
    """로드·검증된 지식베이스."""

    services: list[Service]
    value_matchers: list[ValueMatcher] = field(default_factory=list)

    def __post_init__(self) -> None:
        for s in self.services:
            for c in s.credentials:
                if c.value_regex:
                    self.value_matchers.append(
                        ValueMatcher(s, c, re.compile(c.value_regex))
                    )

    @property
    def credential_count(self) -> int:
        return sum(len(s.credentials) for s in self.services)

    def find(self, service_id: str, kind: str) -> Credential | None:
        for s in self.services:
            if s.service == service_id:
                for c in s.credentials:
                    if c.kind == kind:
                        return c
        return None


def load_knowledge_base(path: Path | str | None = None) -> KnowledgeBase:
    """디렉토리의 모든 *.yaml 을 로드·검증한다.

    경로 우선순위: 명시 인자 > `KEYLENS_KNOWLEDGE_DIR` 환경변수 > 기본(backend/knowledge).
    (패키징된 데스크톱 앱은 번들 위치를 env 로 지정한다.)

    - 스키마 위반은 pydantic ValidationError 로 즉시 실패한다.
    - service·official_env_name 중복은 명시적 에러로 막는다.
    - value_regex 는 컴파일해 잘못된 정규식을 조기에 잡는다.
    """
    if path is None:
        path = os.environ.get("KEYLENS_KNOWLEDGE_DIR") or DEFAULT_KNOWLEDGE_DIR
    directory = Path(path)
    if not directory.is_dir():
        raise FileNotFoundError(f"지식베이스 디렉토리를 찾을 수 없습니다: {directory}")

    services: list[Service] = []
    seen_services: set[str] = set()
    seen_env_names: set[str] = set()

    for f in sorted(directory.glob("*.yaml")):
        # 어떤 파일이 왜 깨졌는지 바로 알 수 있게 파일명을 에러에 붙인다(기동 실패 진단성).
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise ValueError(f"YAML 파싱 실패 ({f.name}): {e}") from e
        try:
            service = Service.model_validate(data)
        except Exception as e:  # pydantic ValidationError 등
            raise ValueError(f"지식베이스 스키마 위반 ({f.name}): {e}") from e

        if service.service in seen_services:
            raise ValueError(f"중복 service id: {service.service!r} ({f.name})")
        seen_services.add(service.service)

        for c in service.credentials:
            if c.official_env_name in seen_env_names:
                raise ValueError(
                    f"중복 official_env_name: {c.official_env_name!r} ({f.name})"
                )
            seen_env_names.add(c.official_env_name)
            if c.value_regex:
                try:
                    re.compile(c.value_regex)  # 잘못된 정규식 조기 검출
                except re.error as e:
                    raise ValueError(
                        f"잘못된 value_regex ({f.name}, {c.kind}): {e}"
                    ) from e

        services.append(service)

    return KnowledgeBase(services=services)
