# 화면 설명 — Tavily 검색 + 로컬 발견 캐시 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 화면 설명 기능(1단계, 이미 구현됨)의 미분류 줄이 지금은 항상 `ai_unverified`(로컬 Ollama
추측만)로 끝나는데, `TAVILY_API_KEY`가 설정돼 있으면 웹 검색으로 그 추측을 확인해 `ai_verified` +
공식 문서 링크까지 붙이고, 사용자가 승인한 추정은 `local_discoveries.yaml`에 캐시해 다음번엔 재검색
없이 재사용한다.

**Architecture:** 미분류 줄마다 (1) 로컬 캐시(정규화된 텍스트 매칭)를 먼저 확인 → 히트하면 Ollama도
Tavily도 안 부름. (2) 캐시 미스면 Ollama에게 라벨 + 서비스명 추측을 물음(기존 프롬프트 확장). (3)
서비스명 추측이 있고 `TAVILY_API_KEY`가 있으면 Tavily로 도메인 제한 없이 검색 → 검색 결과를 다시
Ollama에게 줘서 "진짜 그 서비스 맞는지" 재검증(`ai_verified`) 아니면 원래 추측 그대로
(`ai_unverified`). (4) 사용자가 화면에서 "저장" 누르면 그 줄을 캐시에 append.

**Tech Stack:** 기존 백엔드(FastAPI)·프론트(React+Zustand) 그대로. Tavily 호출도 `ollama_client.py`와
동일하게 표준 라이브러리 `urllib`만 사용 — 새 런타임 의존성 0.

## Global Constraints

- 새로 만드는 모든 파일 맨 위에 SPDX 헤더 2줄(`[Your Name]` 리터럴 그대로).
- 새 런타임 의존성을 추가하지 않는다(Tavily HTTP 호출도 `urllib.request`만).
- 백엔드 테스트는 httpx/`TestClient`를 쓰지 않는다 — 기존 관례대로 함수 직접 호출 +
  `urllib.request.urlopen` monkeypatch(`test_ollama_client.py` 패턴 그대로).
- **Tavily 검색에 도메인 제한을 두지 않는다**(설계 스펙 판단 A — 원본 1단계 설계문서의 "지식베이스
  도메인으로 제한" 문구는 모순이 있어 정정됨). 쿼리 문자열에 "공식 문서" 키워드로 품질을 유도하고,
  검색 결과가 실제로 맞는지는 LLM 재검증으로 판단한다.
- Tavily는 완전 옵트인 — `TAVILY_API_KEY` 없으면 검색 단계 자체를 건너뛰고 기존 1단계 동작
  (`ai_unverified`)과 완전히 동일하게 동작한다. Ollama와 달리 "없으면 버튼이 안 보임"이 아니다.
- 로컬 발견 캐시(`local_discoveries.yaml`)는 자동 저장 안 함 — 사용자가 화면에서 항목별로 승인해야만
  저장. 저장된 항목은 `confirmed: false` 고정, 이 프로젝트 코드로는 절대 `true`로 안 바뀜.
- 캐시 매칭은 OCR 라인 텍스트 정규화 비교(값처럼 보이는 토큰을 `<VALUE>`로 치환)로 한다 — 임베딩
  유사도 등 새 알고리즘/의존성 없음. 정규화는 백엔드에서만 계산(저장·조회 양쪽 다).
- 프론트엔드 검증은 `npx tsc --noEmit -p tsconfig.app.json`(주의: 맨 `npx tsc --noEmit`은 이 레포의
  루트 tsconfig.json이 project-references 솔루션 파일이라 조용히 아무것도 검사하지 않는다) +
  `npm run lint`(oxlint) + `npm run build`. 컴포넌트 자동 테스트 인프라 없음(기존 관례, 새로 안 만듦).
- 설계 근거: `docs/superpowers/specs/2026-08-27-screenshot-explain-tavily-design.md`(이번 작업),
  `docs/superpowers/specs/2026-08-27-screenshot-explain-design.md`(1단계 원본, 판단 5·6 참고 — 판단
  6의 도메인 제한 부분은 위 Global Constraints대로 정정된 버전을 따른다).

---

### Task 1: 백엔드 — `tavily_client.py` (표준 라이브러리 urllib만)

**Files:**
- Create: `backend/app/tavily_client.py`
- Test: `backend/tests/test_tavily_client.py`

**Interfaces:**
- Consumes: 없음(독립 모듈).
- Produces: `TavilyConfig(api_key: str)`. `TavilyConfig.from_env(env: dict[str, str] | None = None) ->
  TavilyConfig | None`(`TAVILY_API_KEY` 없으면 `None`). `search(config: TavilyConfig, query: str,
  max_results: int = 3, timeout: float = 10.0) -> list[dict]` — 각 dict는 `{"title": str, "url": str,
  "content": str}`. **절대 예외를 던지지 않는다** — 실패(네트워크·타임아웃·이상한 응답)는 전부
  빈 리스트 반환(Ollama와 달리 검색 실패가 전체 요청을 막으면 안 되므로 — 설계 스펙 에러 처리 절).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_tavily_client.py`(신규):

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Tavily 검색 클라이언트 — urllib.request.urlopen을 monkeypatch해 실제 네트워크 없이 검증.

ollama_client.py와 달리 이 모듈은 절대 예외를 던지지 않는다(검색 실패는 조용히 빈 리스트로
낮춰지고 전체 /explain/image 요청은 계속 진행돼야 하므로 — 설계 스펙 에러 처리 절 참고).
"""
import io
import json
import urllib.error

from app.tavily_client import TavilyConfig, search

CONFIG = TavilyConfig(api_key="tvly-dummy-key")


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._buf = io.BytesIO(payload)

    def read(self):
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_config_from_env_reads_api_key():
    config = TavilyConfig.from_env({"TAVILY_API_KEY": "tvly-abc123"})
    assert config is not None
    assert config.api_key == "tvly-abc123"


def test_config_from_env_missing_key_returns_none():
    """TAVILY_API_KEY가 없으면 검색 기능 자체가 비활성 — 기본값을 추측하지 않는다."""
    assert TavilyConfig.from_env({}) is None


def test_search_returns_parsed_results(monkeypatch):
    payload = json.dumps(
        {"results": [{"title": "Notion 공식 문서", "url": "https://notion.so/docs", "content": "..."}]}
    ).encode("utf-8")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(payload)
    )
    results = search(CONFIG, "Notion 공식 문서")
    assert results == [{"title": "Notion 공식 문서", "url": "https://notion.so/docs", "content": "..."}]


def test_search_sends_query_and_api_key_in_request_body(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResponse(json.dumps({"results": []}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    search(CONFIG, "OpenAI 공식 문서", max_results=5)
    assert captured["body"]["api_key"] == "tvly-dummy-key"
    assert captured["body"]["query"] == "OpenAI 공식 문서"
    assert captured["body"]["max_results"] == 5
    # 판단 A — 도메인 제한을 걸지 않는다: 요청 바디에 include_domains가 아예 없어야 한다.
    assert "include_domains" not in captured["body"]


def test_search_returns_empty_list_on_connection_error(monkeypatch):
    def raise_error(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", raise_error)
    assert search(CONFIG, "아무 쿼리") == []


def test_search_returns_empty_list_on_malformed_response(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(b"not json")
    )
    assert search(CONFIG, "아무 쿼리") == []


def test_search_returns_empty_list_when_results_key_missing(monkeypatch):
    payload = json.dumps({"unexpected": "shape"}).encode("utf-8")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(payload)
    )
    assert search(CONFIG, "아무 쿼리") == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run (`backend/`에서, **반드시 이 venv의 python 사용**): `.venv/Scripts/python.exe -m pytest
tests/test_tavily_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.tavily_client'`

- [ ] **Step 3: `tavily_client.py` 구현**

`backend/app/tavily_client.py`(신규):

```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/test_tavily_client.py -v`
Expected: PASS(7개 전부)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/tavily_client.py backend/tests/test_tavily_client.py
git commit -m "$(cat <<'EOF'
feat(explain): Tavily 검색 클라이언트(urllib만 사용, 도메인 제한 없음)

TAVILY_API_KEY 없으면 TavilyConfig.from_env()가 None을 반환해
검색 단계가 비활성화된다. search()는 ollama_client와 달리 절대
예외를 던지지 않고 실패 시 빈 리스트를 반환 — 검색 실패가 전체
/explain/image 요청을 막으면 안 되므로. 도메인 제한(include_domains)
은 의도적으로 안 건다(설계 판단 A — 원본 설계의 모순 정정).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: 백엔드 — `discoveries_repo.py` (로컬 발견 캐시 YAML)

**Files:**
- Create: `backend/app/discoveries_repo.py`
- Test: `backend/tests/test_discoveries_repo.py`

**Interfaces:**
- Consumes: 없음(독립 모듈, `PyYAML` 재사용 — 이미 requirements.txt에 있음).
- Produces: `normalize_pattern(text: str) -> str`(값처럼 보이는 토큰을 `<VALUE>`로 치환).
  `find_by_pattern(path: str | Path, pattern: str) -> dict | None`(파일 없으면 `None`).
  `append_discovery(path: str | Path, *, pattern: str, label: str, tier: str, docs_url: str | None) ->
  None`(파일 없으면 새로 생성, `confirmed: false` 고정).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_discoveries_repo.py`(신규):

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""local_discoveries.yaml 읽기/쓰기 — 항상 confirmed: false로 저장되는지, 정규화 매칭이 값은
무시하고 라벨 문구만 비교하는지가 핵심."""
from app.discoveries_repo import append_discovery, find_by_pattern, normalize_pattern


def test_normalize_pattern_replaces_long_alnum_tokens_with_placeholder():
    assert normalize_pattern("API Key: sk-proj-AbCdEfGh12345678") == "API Key: <VALUE>"


def test_normalize_pattern_keeps_short_label_words():
    assert normalize_pattern("Database ID") == "Database ID"


def test_normalize_pattern_collapses_whitespace():
    assert normalize_pattern("API   Key:   sk-proj-AbCdEfGh12345678") == "API Key: <VALUE>"


def test_find_by_pattern_returns_none_when_file_missing(tmp_path):
    path = tmp_path / "local_discoveries.yaml"
    assert find_by_pattern(path, "API Key: <VALUE>") is None


def test_append_then_find_roundtrip(tmp_path):
    path = tmp_path / "local_discoveries.yaml"
    append_discovery(
        path, pattern="API Key: <VALUE>", label="예시 서비스 API 키",
        tier="ai_verified", docs_url="https://example.com/docs",
    )
    found = find_by_pattern(path, "API Key: <VALUE>")
    assert found is not None
    assert found["label"] == "예시 서비스 API 키"
    assert found["tier"] == "ai_verified"
    assert found["docs_url"] == "https://example.com/docs"


def test_appended_entry_is_always_confirmed_false(tmp_path):
    """이 프로젝트 코드로는 절대 confirmed: true로 저장되지 않는다(설계 판단 — 자동 승격 없음)."""
    path = tmp_path / "local_discoveries.yaml"
    append_discovery(
        path, pattern="X", label="Y", tier="ai_unverified", docs_url=None,
    )
    found = find_by_pattern(path, "X")
    assert found["confirmed"] is False


def test_find_by_pattern_no_match_returns_none(tmp_path):
    path = tmp_path / "local_discoveries.yaml"
    append_discovery(path, pattern="A", label="B", tier="ai_unverified", docs_url=None)
    assert find_by_pattern(path, "완전히 다른 패턴") is None


def test_append_multiple_entries_keeps_all(tmp_path):
    path = tmp_path / "local_discoveries.yaml"
    append_discovery(path, pattern="A", label="라벨A", tier="ai_unverified", docs_url=None)
    append_discovery(path, pattern="B", label="라벨B", tier="ai_verified", docs_url=None)
    assert find_by_pattern(path, "A")["label"] == "라벨A"
    assert find_by_pattern(path, "B")["label"] == "라벨B"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discoveries_repo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.discoveries_repo'`

- [ ] **Step 3: `discoveries_repo.py` 구현**

`backend/app/discoveries_repo.py`(신규):

```python
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

import re
from pathlib import Path

import yaml

# 값처럼 보이는 토큰(영숫자·-·_ 6자 이상 연속) — 라벨 문구는 남기고 값만 지운다.
_VALUE_TOKEN = re.compile(r"[A-Za-z0-9_-]{6,}")


def normalize_pattern(text: str) -> str:
    """OCR 라인 텍스트에서 값처럼 보이는 토큰을 <VALUE>로 치환하고 공백을 정규화한다."""
    replaced = _VALUE_TOKEN.sub("<VALUE>", text)
    return " ".join(replaced.split())


def _load(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, list) else []


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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/test_discoveries_repo.py -v`
Expected: PASS(8개 전부)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/discoveries_repo.py backend/tests/test_discoveries_repo.py
git commit -m "$(cat <<'EOF'
feat(explain): 로컬 발견 캐시(local_discoveries.yaml) 읽기/쓰기

정규화(값 토큰 제거)된 OCR 라인 텍스트로 매칭. 항상 confirmed:
false로 저장 — 지식베이스로의 승격은 사람이 PR로 직접 반영하는
것만이 유일한 경로(설계 판단 C).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 백엔드 — `explain.py`에 캐시·Tavily 검증 파이프라인 연결

**Files:**
- Modify: `backend/app/explain.py`
- Test: `backend/tests/test_explain.py`

**Interfaces:**
- Consumes: `tavily_client.TavilyConfig`/`search`(Task 1), `discoveries_repo.normalize_pattern`/
  `find_by_pattern`/`append_discovery`(Task 2).
- Produces: `explain_image()`의 시그니처 확장 —
  `explain_image(image_bytes: bytes, kb: KnowledgeBase, ollama_config: OllamaConfig,
  tavily_config: TavilyConfig | None = None, discoveries_path: str | Path | None = None) ->
  list[ExplainBox]`. 새 파라미터 둘 다 기본값이 있어 **기존 3-인자 호출은 그대로 동작**(기존
  `test_explain.py`의 5개 테스트는 수정 없이 계속 통과해야 함 — Tavily 미설정 상태의 회귀 테스트로
  그대로 남긴다).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_explain.py` 맨 끝(`test_all_boxes_have_valid_rect_coordinates` 뒤)에 추가:

```python
def test_cache_hit_skips_ollama_and_tavily(kb, notion_image, monkeypatch, tmp_path):
    """캐시에 정규화 패턴이 일치하는 항목이 있으면 Ollama도 Tavily도 안 부른다."""
    from app import discoveries_repo, tavily_client

    ollama_calls = []
    tavily_calls = []
    monkeypatch.setattr(
        ollama_client, "generate", lambda *a, **kw: ollama_calls.append(1) or "[]"
    )
    monkeypatch.setattr(
        tavily_client, "search", lambda *a, **kw: tavily_calls.append(1) or []
    )

    cache_path = tmp_path / "local_discoveries.yaml"
    # notion.png의 미분류 줄이 어떤 텍스트인지 몰라도, 캐시가 "모든 정규화 패턴에 일치"하도록
    # find_by_pattern 자체를 monkeypatch해 캐시 히트를 흉내낸다(실제 OCR 텍스트에 의존하지 않음).
    monkeypatch.setattr(
        discoveries_repo, "find_by_pattern",
        lambda path, pattern: {"label": "캐시된 라벨", "tier": "ai_verified", "docs_url": "https://cached.example/docs"},
    )

    boxes = explain.explain_image(
        notion_image, kb, CONFIG, tavily_config=None, discoveries_path=cache_path,
    )

    ai_boxes = [b for b in boxes if b.tier != "known"]
    assert ai_boxes, "미분류 줄이 있어야 캐시 히트를 확인할 수 있음"
    assert all(b.label == "캐시된 라벨" and b.tier == "ai_verified" for b in ai_boxes)
    assert ollama_calls == []
    assert tavily_calls == []


def test_tavily_confirms_guess_produces_ai_verified(kb, notion_image, monkeypatch, tmp_path):
    """Ollama가 서비스명을 추측하고 Tavily 검색 결과가 그 추측을 뒷받침하면 ai_verified."""
    from app import discoveries_repo, tavily_client

    call_count = [0]

    def fake_generate(config, prompt, timeout=30.0):
        call_count[0] += 1
        if call_count[0] == 1:
            # 1차 추론: 라벨 + 서비스명 추측
            return json.dumps([{"index": 0, "label": "안내 문구", "guessed_service": "ExampleCo"}])
        # 2차 추론(검증): 검색 결과가 추측을 뒷받침 → 최종 라벨 + 문서 URL
        assert "ExampleCo" in prompt
        return json.dumps({"label": "ExampleCo 안내", "docs_url": "https://exampleco.example/docs"})

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    monkeypatch.setattr(
        tavily_client, "search",
        lambda config, query, **kw: [{"title": "ExampleCo Docs", "url": "https://exampleco.example/docs", "content": "..."}],
    )
    monkeypatch.setattr(discoveries_repo, "find_by_pattern", lambda path, pattern: None)

    tavily_config = tavily_client.TavilyConfig(api_key="tvly-dummy")
    boxes = explain.explain_image(
        notion_image, kb, CONFIG, tavily_config=tavily_config,
        discoveries_path=tmp_path / "local_discoveries.yaml",
    )

    verified = [b for b in boxes if b.tier == "ai_verified"]
    assert any(b.label == "ExampleCo 안내" and b.docs_url == "https://exampleco.example/docs" for b in verified)


def test_tavily_no_results_falls_back_to_ai_unverified(kb, notion_image, monkeypatch, tmp_path):
    """검색했지만 결과가 없으면(또는 검증 실패) 기존 1차 추론 라벨로 ai_unverified 유지."""
    from app import discoveries_repo, tavily_client

    monkeypatch.setattr(
        ollama_client, "generate",
        lambda *a, **kw: json.dumps([{"index": 0, "label": "안내 문구", "guessed_service": "ExampleCo"}]),
    )
    monkeypatch.setattr(tavily_client, "search", lambda *a, **kw: [])  # 검색 결과 없음
    monkeypatch.setattr(discoveries_repo, "find_by_pattern", lambda path, pattern: None)

    tavily_config = tavily_client.TavilyConfig(api_key="tvly-dummy")
    boxes = explain.explain_image(
        notion_image, kb, CONFIG, tavily_config=tavily_config,
        discoveries_path=tmp_path / "local_discoveries.yaml",
    )

    ai_unverified = [b for b in boxes if b.tier == "ai_unverified"]
    assert any(b.label == "안내 문구" for b in ai_unverified)


def test_no_tavily_config_skips_search_entirely(kb, notion_image, monkeypatch, tmp_path):
    """tavily_config가 None이면(TAVILY_API_KEY 미설정) 검색 단계 자체를 안 부른다 — 1단계 동작 그대로."""
    from app import discoveries_repo, tavily_client

    search_calls = []
    monkeypatch.setattr(
        ollama_client, "generate",
        lambda *a, **kw: json.dumps([{"index": 0, "label": "안내 문구", "guessed_service": "ExampleCo"}]),
    )
    monkeypatch.setattr(tavily_client, "search", lambda *a, **kw: search_calls.append(1) or [])
    monkeypatch.setattr(discoveries_repo, "find_by_pattern", lambda path, pattern: None)

    boxes = explain.explain_image(
        notion_image, kb, CONFIG, tavily_config=None, discoveries_path=tmp_path / "local_discoveries.yaml",
    )
    assert search_calls == []
    assert any(b.tier == "ai_unverified" and b.label == "안내 문구" for b in boxes)
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/test_explain.py -v -k "cache_hit or tavily or no_tavily"`
Expected: FAIL — `TypeError: explain_image() got an unexpected keyword argument 'tavily_config'`

- [ ] **Step 3: `explain.py` 확장**

`backend/app/explain.py` 전체를 다음으로 교체:

```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/test_explain.py -v`
Expected: PASS(기존 5개 + 신규 4개 = 9개 전부)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/explain.py backend/tests/test_explain.py
git commit -m "$(cat <<'EOF'
feat(explain): 미분류 줄 파이프라인에 로컬 캐시 + Tavily 검증 연결

캐시 히트 → Ollama/Tavily 둘 다 스킵. 캐시 미스 → Ollama 1차
추론(라벨+서비스명 추측) → 서비스명 추측 있고 TAVILY_API_KEY
있으면 Tavily 검색(도메인 제한 없음) → 검색 결과로 Ollama 2차
검증 → 확인되면 ai_verified+docs_url, 아니면 기존 ai_unverified
유지. 기존 3-인자 호출(tavily_config=None)은 완전히 하위호환.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 백엔드 — `POST /explain/discoveries` 엔드포인트 + 설정 파일

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/main.py`
- Modify: `.env.example`
- Modify: `.gitignore`
- Test: `backend/tests/test_explain_api.py`

**Interfaces:**
- Consumes: `discoveries_repo.append_discovery`(Task 2), `tavily_client.TavilyConfig`(Task 1).
- Produces: `models.ExplainDiscoveryApprove`(요청 바디: `text, label, tier, docs_url`). 모듈 전역
  `TAVILY_CONFIG: TavilyConfig | None`, `DISCOVERIES_PATH: str`. 라우트
  `async def explain_discoveries_endpoint(body: ExplainDiscoveryApprove) -> None`(204, `known` 등급
  거부 422). 기존 `explain_image_endpoint`가 `TAVILY_CONFIG`/`DISCOVERIES_PATH`를
  `explain.explain_image()`에 같이 넘기도록 수정.

- [ ] **Step 1: `models.py`에 요청 모델 추가**

`backend/app/models.py`의 `ExplainStatusResponse` 클래스(맨 끝) 뒤에 추가:

```python


class ExplainDiscoveryApprove(BaseModel):
    """사용자가 승인한 AI 추정 1건 — local_discoveries.yaml에 append된다(항상 confirmed: false)."""

    text: str
    label: str
    tier: Literal["ai_verified", "ai_unverified"]
    docs_url: Optional[str] = None
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_explain_api.py` 맨 끝(`test_explain_image_endpoint_returns_boxes` 뒤)에 추가:

```python
def test_explain_discoveries_rejects_known_tier(monkeypatch):
    from app.models import ExplainDiscoveryApprove

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            main.explain_discoveries_endpoint(
                ExplainDiscoveryApprove(text="sk-...", label="OpenAI API 키", tier="known", docs_url=None)
            )
        )
    assert exc_info.value.status_code == 422


def test_explain_discoveries_appends_to_cache(monkeypatch, tmp_path):
    from app import discoveries_repo
    from app.models import ExplainDiscoveryApprove

    cache_path = tmp_path / "local_discoveries.yaml"
    monkeypatch.setattr(main, "DISCOVERIES_PATH", str(cache_path))

    asyncio.run(
        main.explain_discoveries_endpoint(
            ExplainDiscoveryApprove(
                text="API Key: abcdefgh12345678", label="예시 서비스 안내",
                tier="ai_verified", docs_url="https://example.com/docs",
            )
        )
    )

    pattern = discoveries_repo.normalize_pattern("API Key: abcdefgh12345678")
    found = discoveries_repo.find_by_pattern(cache_path, pattern)
    assert found is not None
    assert found["label"] == "예시 서비스 안내"
    assert found["confirmed"] is False
```

(파일 맨 위 import 블록에 `from app.models import ...` 관련 줄이 이미 있으면 중복 추가하지 않는다 —
기존 import 스타일을 따라 필요한 이름만 함수 안에서 지역 import 해도 되고, 파일 상단에 모아도 된다.
이 파일의 기존 관례를 확인해서 맞춘다.)

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/test_explain_api.py -v -k discoveries`
Expected: FAIL — `AttributeError: module 'app.main' has no attribute 'explain_discoveries_endpoint'`

- [ ] **Step 4: `main.py`에 엔드포인트 추가**

`backend/app/main.py`의 `from .models import (` 블록에 `ExplainDiscoveryApprove`를 알파벳 순서에 맞게
추가(`ExplainImageResponse` 앞):

```python
    ExplainDiscoveryApprove,
    ExplainImageResponse,
    ExplainStatusResponse,
```

`from .tavily_client import TavilyConfig` 를 `from .ollama_client import OllamaConfig` 줄 뒤에 추가:

```python
from .ocr import OcrUnavailableError, run_ocr
from .ollama_client import OllamaConfig
from .tavily_client import TavilyConfig
from .vault_session import SdkApprovalPending, VaultLocked, VaultRateLimited, VaultService
```

`OLLAMA_CONFIG = OllamaConfig.from_env()` 줄(169번째 줄 부근) 뒤에 추가:

```python
OLLAMA_CONFIG = OllamaConfig.from_env()
TAVILY_CONFIG = TavilyConfig.from_env()
DISCOVERIES_PATH = os.environ.get(
    "KEYLENS_LOCAL_DISCOVERIES_PATH",
    str(Path(__file__).resolve().parent.parent / "local_discoveries.yaml"),
)
```

(`os`와 `Path`는 이미 main.py 상단에 import돼 있는지 확인 — `import os`와 `from pathlib import Path`가
이미 있으면 그대로 재사용, 없으면 추가.)

`explain_image_endpoint` 안의 `explain.explain_image` 호출(197번째 줄 부근):

```python
        boxes = await run_in_threadpool(explain.explain_image, data, KB, OLLAMA_CONFIG)
```

다음으로 교체:

```python
        boxes = await run_in_threadpool(
            explain.explain_image, data, KB, OLLAMA_CONFIG, TAVILY_CONFIG, DISCOVERIES_PATH
        )
```

`explain_image_endpoint` 함수 정의(`return ExplainImageResponse(boxes=boxes)` 다음 줄, 209번째 줄
부근) 뒤에 추가:

```python


@app.post("/explain/discoveries", status_code=204)
async def explain_discoveries_endpoint(body: ExplainDiscoveryApprove) -> None:
    """사용자가 화면에서 승인한 AI 추정 1건을 로컬 발견 캐시에 저장(설계 판단 D)."""
    if body.tier == "known":
        raise HTTPException(status_code=422, detail="known 등급은 저장 대상이 아니에요")
    pattern = discoveries_repo.normalize_pattern(body.text)
    await run_in_threadpool(
        discoveries_repo.append_discovery,
        DISCOVERIES_PATH,
        pattern=pattern, label=body.label, tier=body.tier, docs_url=body.docs_url,
    )
```

`from . import crypto, explain, ollama_client` 줄을 다음으로 교체(discoveries_repo 추가):

```python
from . import crypto, discoveries_repo, explain, ollama_client
```

- [ ] **Step 5: `.env.example`에 안내 추가**

`.env.example`의 `OLLAMA_MODEL=` 줄 다음, `# --- 백엔드 (VAULT-1/2, 구현 완료) ---` 앞에 추가:

```text
# Tavily 검색(옵트인) — 미설정 시 화면 설명은 검색 없이 기존대로 동작(등급만 ai_unverified로 낮아짐).
# 도메인 제한 없음(설계 판단 A). https://tavily.com 에서 발급.
TAVILY_API_KEY=
# 로컬 발견 캐시 경로 재정의(선택). 기본값: backend/local_discoveries.yaml
KEYLENS_LOCAL_DISCOVERIES_PATH=
```

- [ ] **Step 6: `.gitignore`에 추가**

`.gitignore`의 `vault.db` 줄 뒤에 추가:

```text
local_discoveries.yaml
```

- [ ] **Step 7: 테스트 실행 → 통과 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/test_explain_api.py -v`
Expected: PASS(기존 5개 + 신규 2개 = 7개 전부)

Run(전체 회귀): `.venv/Scripts/python.exe -m pytest -q`
Expected: 전부 PASS

- [ ] **Step 8: 커밋**

```bash
git add backend/app/models.py backend/app/main.py backend/tests/test_explain_api.py \
  .env.example .gitignore
git commit -m "$(cat <<'EOF'
feat(explain): POST /explain/discoveries — 승인한 AI 추정 캐시 저장

known 등급은 422로 거부. TAVILY_API_KEY·
KEYLENS_LOCAL_DISCOVERIES_PATH 안내를 .env.example에 추가,
local_discoveries.yaml을 .gitignore에 추가(vault.db와 같은
로컬 전용 런타임 데이터 취급).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 프론트 — API 클라이언트 + 스토어(승인 액션)

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/store/keylensStore.ts`

**Interfaces:**
- Consumes: `ExplainBox`(기존 타입, 변경 없음).
- Produces: `explainDiscoveryApi(box: ExplainBox): Promise<void>`. 상태
  `explainApprovedIndices: Set<number>`(이번 세션에 승인한 박스 인덱스 — 버튼 중복 클릭 방지·UI
  표시용). 액션 `approveDiscovery(index: number): Promise<void>`.

- [ ] **Step 1: `explainDiscoveryApi` 추가**

`frontend/src/api/client.ts`의 `explainImageApi` 함수 정의가 끝나는 지점(`}` 뒤, 파일 끝 근처) 뒤에
추가:

```typescript

/** POST /explain/discoveries — 사용자가 승인한 AI 추정 1건을 로컬 발견 캐시에 저장. */
export async function explainDiscoveryApi(box: ExplainBox, timeoutMs = 10000): Promise<void> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE}/explain/discoveries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: box.text, label: box.label, tier: box.tier, docs_url: box.docs_url ?? null,
      }),
      signal: ctrl.signal,
    })
    if (!res.ok) {
      throw new ApiError(`저장하지 못했어요 (오류 ${res.status}) — 잠시 후 다시 시도해 보세요.`)
    }
  } catch (e) {
    if (e instanceof ApiError) throw e
    throw new ApiError('저장하지 못했어요 — 잠시 후 다시 시도해 보세요.')
  } finally {
    clearTimeout(timer)
  }
}
```

(파일 상단에서 `ApiError`가 이미 같은 파일에 정의돼 있으므로 별도 import 불필요 — `ExplainBox`도
이미 상단 import 블록에 있는지 확인, 없으면 추가.)

- [ ] **Step 2: 상태 필드 추가**

`frontend/src/store/keylensStore.ts`의 `explainBoxes: ExplainBox[]`(111번째 줄 부근) 뒤에 추가:

```typescript
  explainBoxes: ExplainBox[]
  /** 이번 세션에 "저장" 승인한 박스의 인덱스(explainBoxes 배열 기준) — 중복 승인 방지용. */
  explainApprovedIndices: Set<number>
```

- [ ] **Step 3: 액션 타입 선언 추가**

`closeExplain: () => void`(291번째 줄 부근) 뒤에 추가:

```typescript
  closeExplain: () => void
  /** 특정 AI 추정 박스를 로컬 발견 캐시에 저장(사용자 승인). */
  approveDiscovery: (index: number) => Promise<void>
```

- [ ] **Step 4: 초기 상태값 추가**

`explainBoxes: [],`(363번째 줄 부근) 뒤에 추가:

```typescript
    explainBoxes: [],
    explainApprovedIndices: new Set(),
```

- [ ] **Step 5: 액션 구현 + `openExplain`/`closeExplain`에서 초기화**

`openExplain` 구현(1260-1275번째 줄 부근)의 `set({ explainOpen: true, explainLoading: true,
explainBoxes: [] })` 줄을:

```typescript
      set({ explainOpen: true, explainLoading: true, explainBoxes: [] })
```

다음으로 교체(새 요청 시작하면 승인 표시도 초기화):

```typescript
      set({ explainOpen: true, explainLoading: true, explainBoxes: [], explainApprovedIndices: new Set() })
```

`closeExplain: () => set({ explainOpen: false, explainBoxes: [] }),` 줄 뒤에 추가:

```typescript
    closeExplain: () => set({ explainOpen: false, explainBoxes: [] }),
    approveDiscovery: async (index) => {
      const box = get().explainBoxes[index]
      if (!box || box.tier === 'known' || get().explainApprovedIndices.has(index)) return
      try {
        await explainDiscoveryApi(box)
        set((s) => ({ explainApprovedIndices: new Set(s.explainApprovedIndices).add(index) }))
        get().showToast('저장했어요 — 다음번엔 재검색 없이 재사용해요')
      } catch (e) {
        get().showToast(e instanceof ApiError ? e.message : '저장하지 못했어요')
      }
    },
```

`import { ... } from '@/api/client'` 블록에 `explainDiscoveryApi` 추가(`explainImageApi,` 다음 줄):

```typescript
  explainDiscoveryApi,
  explainImageApi,
```

- [ ] **Step 6: 타입 검증**

Run (`frontend/`에서): `npx tsc --noEmit -p tsconfig.app.json`
Expected: 에러 없음.

- [ ] **Step 7: 커밋**

```bash
git add frontend/src/api/client.ts frontend/src/store/keylensStore.ts
git commit -m "$(cat <<'EOF'
feat(explain): 발견 승인 스토어 액션 + API 클라이언트

approveDiscovery — 이미 승인한 박스는 중복 저장 안 함
(explainApprovedIndices). 새 설명 요청 시작하면 승인 표시도
초기화. UI 연결은 다음 커밋에서.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: 프론트 — `ExplainModal`에 "저장" 버튼 + `ai_verified` 등급 표시

**Files:**
- Modify: `frontend/src/components/modals/ExplainModal.tsx`

**Interfaces:**
- Consumes: `approveDiscovery`, `explainApprovedIndices`(Task 5).
- Produces: 없음(UI 전용).

- [ ] **Step 1: 승인 버튼 추가**

`frontend/src/components/modals/ExplainModal.tsx`의 상태 구독 블록(16-21번째 줄):

```typescript
  const open = useKeylens((s) => s.explainOpen)
  const loading = useKeylens((s) => s.explainLoading)
  const boxes = useKeylens((s) => s.explainBoxes)
  const image = useKeylens((s) => s.analyzedImage)
  const close = useKeylens((s) => s.closeExplain)
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null)
```

다음으로 교체:

```typescript
  const open = useKeylens((s) => s.explainOpen)
  const loading = useKeylens((s) => s.explainLoading)
  const boxes = useKeylens((s) => s.explainBoxes)
  const image = useKeylens((s) => s.analyzedImage)
  const close = useKeylens((s) => s.closeExplain)
  const approvedIndices = useKeylens((s) => s.explainApprovedIndices)
  const approveDiscovery = useKeylens((s) => s.approveDiscovery)
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null)
```

박스 라벨 렌더링 부분(`<span ... >{b.label}{docsUrl && ...}</span>`, 63-79번째 줄)의
`{docsUrl && ( ... )}` 뒤(같은 `<span>` 안, `</span>` 태그 앞)에 추가:

```tsx
                  <span
                    className="absolute -top-[18px] left-0 flex items-center gap-[4px] whitespace-nowrap rounded-[3px] px-[4px] text-[10px] font-semibold text-white"
                    style={{ background: style.border.split(' ')[2] }}
                  >
                    {b.label}
                    {docsUrl && (
                      <a
                        href={docsUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="공식 문서 열기"
                        className="underline decoration-dotted underline-offset-2 text-white/90 hover:text-white"
                      >
                        문서
                      </a>
                    )}
                    {b.tier !== 'known' && !approvedIndices.has(i) && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          void approveDiscovery(i)
                        }}
                        title="이 추정을 저장해 다음번에 재검색 없이 재사용"
                        className="cursor-pointer rounded-[2px] bg-white/20 px-[3px] text-white hover:bg-white/35"
                      >
                        저장
                      </button>
                    )}
                    {b.tier !== 'known' && approvedIndices.has(i) && (
                      <span className="text-white/70">✓ 저장됨</span>
                    )}
                  </span>
```

- [ ] **Step 2: 타입/린트/빌드 검증**

Run (`frontend/`에서):
```bash
npx tsc --noEmit -p tsconfig.app.json
npm run lint
npm run build
```
Expected: 셋 다 에러 없이 통과.

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/modals/ExplainModal.tsx
git commit -m "$(cat <<'EOF'
feat(explain): 설명 모달에 발견 저장 버튼 추가

known이 아닌 박스(ai_verified/ai_unverified)에 "저장" 버튼 —
누르면 로컬 발견 캐시에 저장하고 "✓ 저장됨"으로 바뀐다.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: 전체 검증 + 수동 브라우저 확인

**Files:** 없음(검증 전용).

- [ ] **Step 1: 백엔드 전체 회귀**

Run (`backend/`에서): `.venv/Scripts/python.exe -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 2: 프론트 전체 회귀**

Run (`frontend/`에서):
```bash
npx tsc --noEmit -p tsconfig.app.json
npm run lint
npm run build
```
Expected: 셋 다 에러 없이 통과.

- [ ] **Step 3: 수동 브라우저 확인 (Tavily 키가 있을 때)**

`TAVILY_API_KEY`를 실제 셸 환경변수로 export한 뒤(`.env.example` 안내대로 — `.env`에 적는 것만으로는
백엔드에 반영되지 않음) `node scripts/dev.mjs`로 기동:

1. 지식베이스에 없는 새 서비스(예: 실제로 존재하는 아무 SaaS)의 콘솔 스크린샷을 "이 화면 설명해줘"로
   분석 — AI 추정 박스에 🟡(검색 확인, 점선 노란색) 또는 ⚪(미확인, 점선 회색)이 적절히 갈리는지 확인.
2. 🟡 박스에 "문서" 링크가 실제 그 서비스 공식 문서로 연결되는지 확인.
3. AI 추정 박스의 "저장" 클릭 → "✓ 저장됨"으로 바뀌는지, `backend/local_discoveries.yaml`이
   실제로 생성되고 `confirmed: false`로 기록되는지 확인.
4. 같은 화면을 다시 분석 → 저장했던 줄이 Ollama/Tavily 재호출 없이(네트워크 탭에서 Tavily 요청이
   안 나가는지) 캐시에서 바로 나오는지 확인.

- [ ] **Step 4: 수동 브라우저 확인 (Tavily 키 없을 때)**

`TAVILY_API_KEY`를 비우고 재기동 — 기존 1단계 동작과 완전히 동일한지(모든 미분류 줄이
`ai_unverified`) 확인. "이 화면 설명해줘" 버튼 자체는 `OLLAMA_MODEL`만 있으면 여전히 보여야 한다
(Tavily 미설정이 버튼을 숨기면 안 됨).

- [ ] **Step 5: 문제 없으면 최종 보고**

위 확인 항목이 전부 기대대로 동작하면 이 플랜은 완료.
