# SPDX-FileCopyrightText: 2026 ttogle918
# SPDX-License-Identifier: MIT
"""로컬 발견 캐시(local_discoveries.yaml) — 사용자가 승인한 AI 추정만, 항상 confirmed: false.

backend/knowledge/*.yaml(큐레이션된 진짜 지식베이스)과 절대 같은 파일/신뢰도로 섞지 않는다 —
섞으면 LLM이 한 번 잘못 추측한 게 마치 검증된 지식처럼 굳어질 위험이 있다. 이 파일 안의 confirmed는
이 프로젝트 코드로는 절대 true로 바뀌지 않는다 — 지식베이스로의 승격은 사람이 knowledge/*.yaml에
직접 PR로 반영하는 것만이 유일한 경로다.

설계 근거: docs/superpowers/specs/2026-08-27-screenshot-explain-tavily-design.md 판단 C.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

# 값처럼 보이는 토큰(영숫자·-·_ 6자 이상 연속, 최소 하나의 -·_·숫자 포함) — 라벨 문구는 남기고 값만 지운다.
_VALUE_TOKEN = re.compile(r"(?=[A-Za-z0-9_-]*[0-9_-])[A-Za-z0-9_-]{6,}")


def normalize_pattern(text: str) -> str:
    """OCR 라인 텍스트에서 값처럼 보이는 토큰을 <VALUE>로 치환하고 공백을 정규화한다."""
    replaced = _VALUE_TOKEN.sub("<VALUE>", text)
    return " ".join(replaced.split())


def _load(path: str | Path) -> list[dict]:
    """캐시 파일을 읽는다. 손상된 파일(깨진 YAML·잘못된 모양)은 예외 대신 빈 목록으로 낮춘다 —
    이 파일은 .gitignore 대상 로컬 상태라 수동 편집·쓰기 도중 중단으로 깨질 수 있다."""
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError:
            return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def find_by_pattern(path: str | Path, pattern: str) -> dict | None:
    """정규화된 패턴이 정확히 일치하는 캐시 항목을 찾는다. 없으면 None."""
    for entry in _load(path):
        if entry.get("pattern") == pattern:
            return entry
    return None


def append_discovery(
    path: str | Path,
    *,
    pattern: str,
    label: str,
    tier: str,
    docs_url: str | None,
) -> None:
    """사용자가 승인한 추정 1건을 append한다. confirmed는 항상 false로 고정."""
    p = Path(path)
    entries = _load(p)
    entries.append(
        {"pattern": pattern, "label": label, "tier": tier, "docs_url": docs_url, "confirmed": False}
    )
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(entries, f, allow_unicode=True, sort_keys=False)
