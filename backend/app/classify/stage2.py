# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Stage 2 — 맥락 기반 분류 (SPEC 4.3, KeyLens의 차별점).

값만으로 애매한 값(UUID·32 hex)을 **출처 맥락**으로 가려낸다.
- 라벨 신호: 값 주변 텍스트("Database ID", "REST API 키")를 지식베이스 label_patterns 와 대조.
- URL 신호: 입력 URL을 서비스 url_patterns 와 대조해 위치로 종류 도출.
신호가 한 종류를 가리키면 분류하고, 여러 종류로 갈리면 단정하지 않고 conflict(확인 필요)로 표시한다.
OCR(CORE-3)은 이 파이프라인에 "이미지→텍스트+라벨"을 먹이는 입력 경로일 뿐 — 여기서는 text·url 로 동작.
"""
from __future__ import annotations

import re

from ..knowledge import KnowledgeBase
from ..masking import mask
from ..models import ClassifiedItem, ConflictOption, Credential, Service

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX32_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")


def _fmt(value: str) -> str:
    if _UUID_RE.fullmatch(value):
        return "UUID"
    if len(value) == 32:
        return "32자리 hex"
    return f"{len(value)}자 문자열"


def _find_ambiguous(text: str) -> list[str]:
    """텍스트에서 값 기반으로 애매한 값(UUID·32hex)을 등장 순서로 수집(중복 제거)."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _UUID_RE.finditer(text):
        v = m.group(0)
        if v not in seen:
            seen.add(v)
            out.append(v)
    for m in _HEX32_RE.finditer(text):
        v = m.group(0)
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _context_for(text: str, value: str) -> str:
    """값이 있는 줄 + 바로 위 비어있지 않은 줄을 라벨 컨텍스트로 반환."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if value in line:
            ctx = line
            for k in range(i - 1, -1, -1):
                if lines[k].strip():
                    ctx = lines[k] + " · " + ctx
                    break
            return ctx
    return ""


# 하나의 값에 대한 신호: (서비스, 자격증명, 근거, 강한신호 여부)
_Signal = tuple[Service, Credential, str, bool]


def _label_candidates(context: str, kb: KnowledgeBase) -> list[_Signal]:
    """컨텍스트 텍스트에서 label_patterns 매칭(값 기반이 아닌 종류만)."""
    out: list[_Signal] = []
    low = context.lower()
    for s in kb.services:
        for c in s.credentials:
            if c.value_regex:  # 값 기반 종류는 Stage1 담당
                continue
            for pat in c.label_patterns:
                if pat.lower() in low:
                    out.append((s, c, f'라벨 "{pat}" 감지', True))
                    break
    return out


def _url_candidates(url: str, kb: KnowledgeBase) -> list[tuple[Service, Credential, str, str, bool]]:
    """URL을 url_patterns 와 대조. 반환: (서비스, 자격증명, 값, 근거, 강한신호)."""
    out: list[tuple[Service, Credential, str, str, bool]] = []
    for s in kb.services:
        for c in s.credentials:
            for pat in c.url_patterns:
                m = re.search(pat, url)
                if m and m.groups():
                    value = m.group(1)
                    # 마지막 경로 세그먼트(page_id)는 위치 신호라 약하게, 명시 구조(?v= 등)는 강하게.
                    strong = c.kind != "page_id"
                    out.append((s, c, value, "URL 구조 매칭", strong))
    return out


def classify_context(
    text: str, url: str, kb: KnowledgeBase, skip_values: set[str] | None = None
) -> list[ClassifiedItem]:
    """text 라벨 + url 구조 신호로 애매한 값을 분류한다."""
    skip = skip_values or set()
    signals: dict[str, list[_Signal]] = {}

    def add(value: str, sig: _Signal) -> None:
        signals.setdefault(value, []).append(sig)

    if text:
        for value in _find_ambiguous(text):
            if value in skip:
                continue
            ctx = _context_for(text, value)
            for sig in _label_candidates(ctx, kb):
                add(value, sig)

    if url:
        for s, c, value, evidence, strong in _url_candidates(url, kb):
            if value in skip:
                continue
            add(value, (s, c, evidence, strong))

    items: list[ClassifiedItem] = []
    for value, cands in signals.items():
        # official_env_name 기준으로 종류를 압축(같은 종류면 강한 신호 우선).
        by_env: dict[str, _Signal] = {}
        for s, c, ev, strong in cands:
            key = c.official_env_name
            if key not in by_env or (strong and not by_env[key][3]):
                by_env[key] = (s, c, ev, strong)
        distinct = list(by_env.values())

        if len(distinct) == 1:
            s, c, ev, strong = distinct[0]
            items.append(
                ClassifiedItem(
                    value=value,
                    # Stage2 대상(UUID·hex)은 공개 접두어가 없다 → 노출 축소
                    masked=mask(value, keep_front=4),
                    service=s.service,
                    display_name=s.display_name,
                    kind=c.kind,
                    label=c.label,
                    official_env_name=c.official_env_name,
                    confidence="high" if strong else "medium",
                    format=_fmt(value),
                    source="맥락 · 라벨/URL",
                    stage=2,
                    meta={"detected_by": "context", "evidence": ev},
                )
            )
        else:
            # 신호 충돌 — 단정 금지, 사용자에게 선택지 제시.
            ordered = sorted(distinct, key=lambda x: not x[3])  # 강한 신호 먼저
            options = [
                ConflictOption(
                    kind=c.kind,
                    label=c.label,
                    official_env_name=c.official_env_name,
                    evidence=ev,
                    signal="신호 강함" if strong else "신호 약함",
                    strong=strong,
                )
                for _s, c, ev, strong in ordered
            ]
            svc = ordered[0][0]
            items.append(
                ClassifiedItem(
                    value=value,
                    masked=mask(value, keep_front=4),
                    service=svc.service,
                    display_name=svc.display_name,
                    kind="ambiguous",
                    label="종류 미확정",
                    official_env_name=None,
                    confidence="low",
                    format=_fmt(value),
                    source="맥락 · 신호 충돌",
                    stage=2,
                    conflict=True,
                    options=options,
                    meta={"detected_by": "context", "conflict": True},
                )
            )

    return items
