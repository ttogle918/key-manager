# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""로컬 발견 캐시(local_discoveries.yaml) — 사용자가 승인한 AI 추정만, 항상 confirmed: false.

backend/knowledge/*.yaml(큐레이션된 진짜 지식베이스)과 절대 같은 파일/신뢰도로 섞지 않는다 —
섞으면 LLM이 한 번 잘못 추측한 게 마치 검증된 지식처럼 굳어질 위험이 있다. 이 파일 안의 confirmed는
이 프로젝트 코드로는 절대 true로 바뀌지 않는다 — 지식베이스로의 승격은 사람이 knowledge/*.yaml에
직접 PR로 반영하는 것만이 유일한 경로다.

설계 근거: docs/superpowers/specs/2026-08-27-screenshot-explain-tavily-design.md 판단 C.
"""
from __future__ import annotations

import os
import re
import threading
from pathlib import Path

import yaml

# 값처럼 보이는 토큰 후보(영숫자·-·_ 6자 이상 연속) — 실제로 값인지는 _looks_like_value()가 판단한다.
_VALUE_TOKEN = re.compile(r"[A-Za-z0-9_-]{6,}")
_HEX_ONLY = re.compile(r"^[0-9a-fA-F]+$")

_REQUIRED_KEYS = ("pattern", "label", "tier")
_VALID_TIERS = ("known", "ai_verified", "ai_unverified")

# append_discovery()의 read-modify-write 구간을 프로세스 내에서 직렬화 — 짧은 시간에 여러 건을
# 승인해도(예: "저장" 버튼 연타) 동시 쓰기로 항목이 유실되지 않게 한다.
_write_lock = threading.Lock()


def _looks_like_value(token: str) -> bool:
    """토큰이 라벨 문구가 아니라 값(시크릿 등)처럼 보이는지 판단.

    숫자가 하나라도 있으면 값으로 간주(대부분의 실제 키·ID는 숫자를 포함) — "Project_ID"·
    "Database_ID" 같이 `_`만 포함한 라벨 문구는 숫자가 없어 더 이상 지워지지 않는다(과거엔 지워져서
    서로 다른 라벨이 동일한 <VALUE> 패턴으로 뭉개졌다). 숫자가 없어도 8자 이상 순수 16진수 문자열은
    (예: "deadbeefcafebabe") 값으로 간주 — 흔한 라벨 단어는 이 조건에 안 걸린다.
    """
    if any(c.isdigit() for c in token):
        return True
    return len(token) >= 8 and bool(_HEX_ONLY.match(token))


def normalize_pattern(text: str) -> str:
    """OCR 라인 텍스트에서 값처럼 보이는 토큰을 <VALUE>로 치환하고 공백을 정규화한다."""
    replaced = _VALUE_TOKEN.sub(lambda m: "<VALUE>" if _looks_like_value(m.group(0)) else m.group(0), text)
    return " ".join(replaced.split())


def _is_valid_entry(entry: dict) -> bool:
    """필수 키가 다 있고 tier가 알려진 값인지 확인 — 손상되거나 사람이 잘못 손댄 항목이 파이프라인을
    깨뜨리지 않도록(ExplainBox 생성 시 KeyError/Pydantic ValidationError로 이어질 수 있었음) 조회
    시점에 걸러낸다."""
    if not all(key in entry for key in _REQUIRED_KEYS):
        return False
    if not isinstance(entry.get("pattern"), str) or not isinstance(entry.get("label"), str):
        return False
    return entry.get("tier") in _VALID_TIERS


def _load(path: str | Path) -> list[dict]:
    """캐시 파일을 읽는다. 손상된 파일(깨진 YAML·잘못된 모양·불완전한 항목)은 예외 대신 빈
    목록/부분 목록으로 낮춘다 — 이 파일은 .gitignore 대상 로컬 상태라 수동 편집·쓰기 도중 중단으로
    깨질 수 있다."""
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
    return [entry for entry in data if isinstance(entry, dict) and _is_valid_entry(entry)]


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
    """사용자가 승인한 추정 1건을 append한다. confirmed는 항상 false로 고정.

    임시 파일에 다 쓴 뒤 os.replace()로 교체(원자적 — 쓰다가 중단돼도 기존 파일이 반쪽짜리로
    남지 않는다) + 프로세스 내 락으로 동시 호출 시 read-modify-write 경합으로 항목이 유실되는
    것을 막는다.
    """
    p = Path(path)
    with _write_lock:
        entries = _load(p)
        entries.append(
            {"pattern": pattern, "label": label, "tier": tier, "docs_url": docs_url, "confirmed": False}
        )
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            yaml.safe_dump(entries, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp, p)
