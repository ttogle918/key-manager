# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""화면 설명 기능 — OCR 줄들을 지식베이스 대조로 먼저 라벨링하고, 남은 미분류 줄은 로컬 발견
캐시 → 로컬 Ollama → (옵션) Tavily 검색 검증 순으로 처리한다.

설계 근거:
- docs/superpowers/specs/2026-08-27-screenshot-explain-design.md (1단계 원본)
- docs/superpowers/specs/2026-08-27-screenshot-explain-tavily-design.md (Tavily·캐시 구체화)
"""
from __future__ import annotations

import json
from pathlib import Path

from . import discoveries_repo, ollama_client, tavily_client
from .classify.pipeline import analyze
from .knowledge import KnowledgeBase
from .models import AnalyzeRequest, ExplainBox
from .ocr import run_ocr_lines
from .ollama_client import OllamaConfig
from .tavily_client import TavilyConfig

_UNKNOWN_LABEL = "알 수 없음"

_GUESS_PROMPT_TEMPLATE = """다음은 스크린샷에서 인식됐지만 아직 어떤 서비스의 값인지 모르는 텍스트 줄입니다.
각 줄이 화면에서 어떤 역할을 하는지 한국어로 아주 짧게(15자 이내) 설명하세요. 정말 모르겠으면
"{unknown}"이라고 답하세요. 절대 값 자체를 지어내거나 추측해서 새로 만들지 마세요 — 이 줄이
"무엇인지"만 설명하세요. 이 줄이 특정 서비스/제품의 화면처럼 보이면 그 서비스명도 추측해서
guessed_service에 적으세요(모르면 null).

{lines}

아래 JSON 배열 형식으로만 답하세요(다른 설명 없이, 마크다운 코드블록도 쓰지 마세요):
[{{"index": 0, "label": "...", "guessed_service": "..." 또는 null}}, ...]
"""

_VERIFY_PROMPT_TEMPLATE = """다음은 스크린샷에서 발견된 텍스트 줄과, 이게 "{guessed_service}"라는
서비스일 것이라는 추측을 뒷받침하는 웹 검색 결과입니다.

원본 텍스트 줄: "{line_text}"
추측한 서비스: {guessed_service}

검색 결과:
{search_results}

검색 결과가 실제로 "{guessed_service}"의 공식 문서·홈페이지를 가리키면, 이 줄이 화면에서 어떤
역할을 하는지 한국어로 아주 짧게(15자 이내) 설명하고 가장 적절한 공식 문서 URL을 고르세요. 검색
결과가 추측을 뒷받침하지 않으면(관련 없거나 불확실하면) label을 "{unknown}"으로, docs_url을
null로 답하세요.

아래 JSON으로만 답하세요(다른 설명 없이, 마크다운 코드블록도 쓰지 마세요):
{{"label": "...", "docs_url": "..." 또는 null}}
"""


def _bbox(box: list[list[float]]) -> tuple[float, float, float, float]:
    """4점 폴리곤 → 축 정렬 사각형 (x, y, w, h)."""
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    x0, y0 = min(xs), min(ys)
    return x0, y0, max(xs) - x0, max(ys) - y0


def _parse_guess_labels(raw: str) -> dict[int, dict]:
    """1차 추론 응답에서 JSON 배열만 뽑아 {index: {label, guessed_service}} 로 변환."""
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        return {}
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, list):
        return {}
    out: dict[int, dict] = {}
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        idx, label = entry.get("index"), entry.get("label")
        if isinstance(idx, int) and isinstance(label, str) and label.strip():
            guessed = entry.get("guessed_service")
            out[idx] = {
                "label": label.strip(),
                "guessed_service": guessed.strip() if isinstance(guessed, str) and guessed.strip() else None,
            }
    return out


def _parse_verify_result(raw: str) -> dict | None:
    """2차(검증) 추론 응답에서 {label, docs_url} 객체만 뽑는다. 형식이 이상하면 None."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    label = parsed.get("label")
    if not isinstance(label, str) or not label.strip():
        return None
    docs_url = parsed.get("docs_url")
    return {"label": label.strip(), "docs_url": docs_url if isinstance(docs_url, str) else None}


def _ask_ollama_guess(config: OllamaConfig, unknown_lines: list[dict]) -> dict[int, dict]:
    """미분류 줄들에 대해 라벨 + 서비스명 추측을 한 번에 요청한다.

    연결 실패(OllamaUnavailableError)는 여기서 삼키지 않고 그대로 위로 전파한다 — "Ollama가 아예
    안 떠 있다"는 사실이 "모델이 이 줄을 모른다"는 것과 다른 문제이기 때문(설계 스펙 에러 처리 절).
    """
    if not unknown_lines:
        return {}
    numbered = "\n".join(f"[{i}] {line['text']}" for i, line in enumerate(unknown_lines))
    prompt = _GUESS_PROMPT_TEMPLATE.format(unknown=_UNKNOWN_LABEL, lines=numbered)
    raw = ollama_client.generate(config, prompt)
    return _parse_guess_labels(raw)


def _verify_with_search(
    ollama_config: OllamaConfig, tavily_config: TavilyConfig, line_text: str, guessed_service: str
) -> dict | None:
    """Tavily로 검색 → 결과를 Ollama에게 다시 줘서 검증. 검색 결과가 없거나 검증 실패면 None.

    Tavily search()는 예외를 던지지 않으므로(설계 판단) 여기서 별도 try/except 불필요. Ollama
    2차 호출이 실패(OllamaUnavailableError)하면 그대로 위로 전파한다 — 1차 호출과 동일 정책.
    """
    results = tavily_client.search(tavily_config, f"{guessed_service} 공식 문서")
    if not results:
        return None
    search_text = "\n".join(f"- {r['title']} ({r['url']}): {r['content'][:200]}" for r in results)
    prompt = _VERIFY_PROMPT_TEMPLATE.format(
        guessed_service=guessed_service, line_text=line_text,
        search_results=search_text, unknown=_UNKNOWN_LABEL,
    )
    raw = ollama_client.generate(ollama_config, prompt)
    verified = _parse_verify_result(raw)
    if verified is None or verified["label"] == _UNKNOWN_LABEL:
        return None
    return verified


def explain_image(
    image_bytes: bytes,
    kb: KnowledgeBase,
    ollama_config: OllamaConfig,
    tavily_config: TavilyConfig | None = None,
    discoveries_path: str | Path | None = None,
) -> list[ExplainBox]:
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

    # 캐시 확인 — 히트한 줄은 Ollama/Tavily를 건너뛴다.
    cached_boxes: list[ExplainBox] = []
    remaining: list[dict] = []
    for line in unknown_lines:
        pattern = discoveries_repo.normalize_pattern(line["text"])
        hit = discoveries_repo.find_by_pattern(discoveries_path, pattern) if discoveries_path else None
        if hit is None:
            remaining.append(line)
            continue
        x, y, w, h = _bbox(line["box"])
        cached_boxes.append(
            ExplainBox(x=x, y=y, w=w, h=h, text=line["text"], label=hit["label"], tier=hit["tier"], docs_url=hit.get("docs_url"))
        )

    guesses = _ask_ollama_guess(ollama_config, remaining)
    ai_boxes: list[ExplainBox] = []
    for i, line in enumerate(remaining):
        guess = guesses.get(i, {"label": _UNKNOWN_LABEL, "guessed_service": None})
        x, y, w, h = _bbox(line["box"])
        label, tier, docs_url = guess["label"], "ai_unverified", None

        if tavily_config is not None and guess["guessed_service"]:
            verified = _verify_with_search(ollama_config, tavily_config, line["text"], guess["guessed_service"])
            if verified is not None:
                label, tier, docs_url = verified["label"], "ai_verified", verified["docs_url"]

        ai_boxes.append(ExplainBox(x=x, y=y, w=w, h=h, text=line["text"], label=label, tier=tier, docs_url=docs_url))

    return known + cached_boxes + ai_boxes
