# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""분류 파이프라인 — 입력을 Stage1 로 처리한다.

Stage2(라벨·URL 맥락)와 OCR 은 후속 스프린트에서 이 자리에 연결한다 (SPEC 4.3 / 5.2).
"""
from __future__ import annotations

from ..knowledge import KnowledgeBase
from ..models import AnalyzeRequest, AnalyzeResponse, ClassifiedItem
from .stage1 import classify_text


def analyze(request: AnalyzeRequest, kb: KnowledgeBase) -> AnalyzeResponse:
    collected: list[ClassifiedItem] = []

    if request.text:
        collected.extend(classify_text(request.text, kb, source_label="텍스트"))
    if request.url:
        # Stage1 은 URL 문자열에서 접두어 키만 훑는다. URL 구조 기반 판별은 Stage2 담당.
        collected.extend(classify_text(request.url, kb, source_label="URL"))

    # 텍스트+URL 교차 중복 제거 (값 기준, 첫 항목 유지)
    seen: set[str] = set()
    items: list[ClassifiedItem] = []
    for it in collected:
        if it.value in seen:
            continue
        seen.add(it.value)
        items.append(it)

    return AnalyzeResponse(items=items, count=len(items))
