# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Tavily 웹 검색 클라이언트 — 표준 라이브러리 urllib만 사용(새 런타임 의존성 0).

ollama_client.py와 달리 이 모듈은 절대 예외를 던지지 않는다 — 검색 실패(키 없음·네트워크·타임아웃·
이상한 응답)는 전부 빈 리스트로 조용히 낮춰지고, 호출자는 그걸 "검색 결과 없음"과 동일하게 취급해
ai_unverified로 폴백한다(전체 /explain/image 요청은 계속 진행). 도메인 제한(include_domains)은
의도적으로 걸지 않는다 — 설계 근거:
docs/superpowers/specs/2026-08-27-screenshot-explain-tavily-design.md 판단 A.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_SEARCH_URL = "https://api.tavily.com/search"


class TavilyConfig:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "TavilyConfig | None":
        """TAVILY_API_KEY가 없으면 None — 검색 단계 자체가 비활성화된다."""
        e = env if env is not None else os.environ
        api_key = e.get("TAVILY_API_KEY")
        if not api_key:
            return None
        return cls(api_key=api_key)


def search(config: TavilyConfig, query: str, max_results: int = 3, timeout: float = 10.0) -> list[dict]:
    """쿼리로 검색해 {title, url, content} 목록을 반환. 실패하면 항상 빈 리스트(예외 안 던짐)."""
    body = json.dumps(
        {"api_key": config.api_key, "query": query, "max_results": max_results}
    ).encode("utf-8")
    req = urllib.request.Request(
        _SEARCH_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    out: list[dict] = []
    for r in results:
        if isinstance(r, dict) and isinstance(r.get("title"), str) and isinstance(r.get("url"), str):
            out.append({"title": r["title"], "url": r["url"], "content": r.get("content", "")})
    return out
