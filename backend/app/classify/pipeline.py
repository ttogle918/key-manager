# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""분류 파이프라인 — Stage1(값 기반) → Stage2(맥락 기반) 병합.

- Stage1: 텍스트에서 접두어가 명확한 키를 즉시 식별.
- Stage2: 값만으로 애매한 값(UUID·32hex)을 텍스트 라벨 + URL 구조로 가려낸다.
OCR(CORE-3)은 이후 "이미지 → 텍스트+라벨"을 만들어 이 파이프라인에 먹인다.
"""
from __future__ import annotations

from ..knowledge import KnowledgeBase
from ..models import AnalyzeRequest, AnalyzeResponse, ClassifiedItem
from .stage1 import classify_text
from .stage2 import classify_context


def analyze(request: AnalyzeRequest, kb: KnowledgeBase) -> AnalyzeResponse:
    text = request.text or ""
    url = request.url or ""

    # Stage1: 값 기반(텍스트만). URL 문자열 자체는 Stage2(url_patterns)가 다룬다.
    stage1 = classify_text(text, kb, source_label="텍스트") if text else []
    high_values = {it.value for it in stage1 if it.confidence == "high"}

    # Stage2: 맥락 기반. Stage1이 이미 확정(high)한 값은 건너뛴다.
    stage2 = classify_context(text, url, kb, skip_values=high_values)

    # 값 기준 병합: 같은 값이면 Stage2가 Stage1 unknown 을 대체(더 나은 답). 순서는 첫 등장 유지.
    order: list[str] = []
    by_value: dict[str, ClassifiedItem] = {}
    for it in [*stage1, *stage2]:
        if it.value not in by_value:
            order.append(it.value)
        by_value[it.value] = it

    items = [by_value[v] for v in order]
    return AnalyzeResponse(items=items, count=len(items))
