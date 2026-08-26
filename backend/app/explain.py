# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""화면 설명 기능(1단계) — OCR 줄들을 지식베이스 대조로 먼저 라벨링하고,
남은 미분류 줄만 로컬 Ollama에게 짧은 설명을 요청한다.

설계 근거: docs/superpowers/specs/2026-08-27-screenshot-explain-design.md
"""
from __future__ import annotations

import json

from . import ollama_client
from .classify.pipeline import analyze
from .knowledge import KnowledgeBase
from .models import AnalyzeRequest, ExplainBox
from .ocr import run_ocr_lines
from .ollama_client import OllamaConfig, OllamaUnavailableError

_UNKNOWN_LABEL = "알 수 없음"

_PROMPT_TEMPLATE = """다음은 스크린샷에서 인식됐지만 아직 어떤 서비스의 값인지 모르는 텍스트 줄입니다.
각 줄이 화면에서 어떤 역할을 하는지 한국어로 아주 짧게(15자 이내) 설명하세요. 정말 모르겠으면
"{unknown}"이라고 답하세요. 절대 값 자체를 지어내거나 추측해서 새로 만들지 마세요 — 이 줄이
"무엇인지"만 설명하세요.

{lines}

아래 JSON 배열 형식으로만 답하세요(다른 설명 없이, 마크다운 코드블록도 쓰지 마세요):
[{{"index": 0, "label": "..."}}, ...]
"""


def _bbox(box: list[list[float]]) -> tuple[float, float, float, float]:
    """4점 폴리곤 → 축 정렬 사각형 (x, y, w, h)."""
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    x0, y0 = min(xs), min(ys)
    return x0, y0, max(xs) - x0, max(ys) - y0


def _parse_labels(raw: str) -> dict[int, str]:
    """Ollama 응답에서 JSON 배열만 뽑아 {index: label} 로 변환. 뭐든 이상하면 빈 dict."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, list):
        return {}
    labels: dict[int, str] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        idx, label = entry.get("index"), entry.get("label")
        if isinstance(idx, int) and isinstance(label, str) and label.strip():
            labels[idx] = label.strip()
    return labels


def _ask_ollama(config: OllamaConfig, unknown_lines: list[dict]) -> dict[int, str]:
    if not unknown_lines:
        return {}
    numbered = "\n".join(f"[{i}] {line['text']}" for i, line in enumerate(unknown_lines))
    prompt = _PROMPT_TEMPLATE.format(unknown=_UNKNOWN_LABEL, lines=numbered)
    try:
        raw = ollama_client.generate(config, prompt)
    except OllamaUnavailableError:
        return {}
    return _parse_labels(raw)


def explain_image(image_bytes: bytes, kb: KnowledgeBase, config: OllamaConfig) -> list[ExplainBox]:
    lines = run_ocr_lines(image_bytes)
    text = "\n".join(line["text"] for line in lines)
    resp = analyze(AnalyzeRequest(text=text), kb)

    known: list[ExplainBox] = []
    unknown_lines: list[dict] = []
    for line in lines:
        match = next((it for it in resp.items if it.value and it.value in line["text"]), None)
        if match is None:
            unknown_lines.append(line)
            continue
        cred = kb.find(match.service, match.kind) if match.service and match.kind else None
        x, y, w, h = _bbox(line["box"])
        known.append(
            ExplainBox(
                x=x, y=y, w=w, h=h,
                text=line["text"],
                label=match.display_name or match.official_env_name or match.kind,
                tier="known",
                docs_url=cred.docs_url if cred else None,
            )
        )

    labels = _ask_ollama(config, unknown_lines)
    ai_boxes: list[ExplainBox] = []
    for i, line in enumerate(unknown_lines):
        x, y, w, h = _bbox(line["box"])
        ai_boxes.append(
            ExplainBox(
                x=x, y=y, w=w, h=h,
                text=line["text"],
                label=labels.get(i, _UNKNOWN_LABEL),
                tier="ai_unverified",
                docs_url=None,
            )
        )

    return known + ai_boxes
