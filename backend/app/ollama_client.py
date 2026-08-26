# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""로컬 Ollama HTTP 클라이언트 — 표준 라이브러리 urllib만 사용(새 런타임 의존성 0).

앱은 어떤 LLM 모델도 번들하지 않는다 — 사용자가 이미 설치·실행 중인 Ollama에만 연결한다(옵트인).
설계 근거: docs/superpowers/specs/2026-08-27-screenshot-explain-design.md 판단 3.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaUnavailableError(RuntimeError):
    """Ollama에 연결할 수 없거나 응답 형식이 예상과 다를 때."""


class OllamaConfig:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "OllamaConfig | None":
        """OLLAMA_MODEL이 없으면 None — 기능을 비활성화한다(기본 모델을 추측하지 않음)."""
        e = env if env is not None else os.environ
        model = e.get("OLLAMA_MODEL")
        if not model:
            return None
        return cls(base_url=e.get("OLLAMA_BASE_URL", DEFAULT_BASE_URL), model=model)


def is_available(config: OllamaConfig, timeout: float = 2.0) -> bool:
    """Ollama가 떠 있는지 가벼운 헬스체크(모델 목록 조회 엔드포인트)."""
    try:
        req = urllib.request.Request(f"{config.base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError):
        return False


def generate(config: OllamaConfig, prompt: str, timeout: float = 30.0) -> str:
    """프롬프트 하나를 보내고 전체 응답 텍스트를 받는다(스트리밍 없음)."""
    body = json.dumps({"model": config.model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{config.base_url}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        raise OllamaUnavailableError(f"Ollama 요청 실패: {e}") from e
    response = payload.get("response")
    if not isinstance(response, str):
        raise OllamaUnavailableError("Ollama 응답 형식이 예상과 다릅니다")
    return response
