<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# 화면 영역별 AI 설명 — 1단계(OCR 박스 + 로컬 Ollama) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스크린샷의 각 줄이 이미 아는 서비스면 지식베이스 정보를, 모르는 서비스면 로컬 Ollama의
짧은 추측을 박스로 짚어가며 보여주는 "이 화면 설명해줘" 기능의 1단계(검색·캐시 없음)를 구현한다.

**Architecture:** 백엔드 RapidOCR이 이미 계산하는 줄 단위 박스 좌표를 보존해 새 `/explain/image`
엔드포인트에서 반환한다. 지식베이스에 이미 있는 줄은 기존 Stage1/2 분류 결과로 즉시 라벨링하고,
없는 줄만 로컬 Ollama(옵트인, 미설정 시 기능 자체 숨김)에게 짧은 설명을 요청한다. 프론트엔드는
새 모달에서 스크린샷을 원본 크기로 보여주고 그 위에 박스+라벨을 오버레이한다.

**Tech Stack:** 백엔드는 표준 라이브러리 `urllib`만으로 Ollama HTTP API(`/api/tags`, `/api/generate`)
호출(새 런타임 의존성 0). 프론트는 기존 React + TypeScript + Zustand 스택 그대로.

**설계 스펙:** `docs/superpowers/specs/2026-08-27-screenshot-explain-design.md`(2·3단계는 각각
Tavily 검색 연동, 로컬 발견 캐시+승인 흐름을 다루는 별도 계획으로 이어진다 — 이 계획은 1단계만).

## Global Constraints

- SPDX 헤더 2줄을 새로 만드는 모든 파일 맨 위에 붙인다(`[Your Name]` 리터럴 플레이스홀더 — 실제
  이름으로 바꾸지 않는다. 이 레포 전역 관례).
- **httpx/`TestClient`를 쓰지 않는다** — `certifi`(MPL-2.0) 라이선스 문제로 이 레포에서 금지된
  패턴(`backend/requirements-dev.txt`에 명시). 라우트 함수는 직접 호출해서 테스트한다
  (`backend/tests/test_vault_api.py` 패턴).
- 새 런타임 의존성을 추가하지 않는다 — Ollama 호출은 표준 라이브러리 `urllib.request`만 쓴다.
- 앱은 어떤 LLM 모델도 번들하지 않는다 — 사용자가 이미 실행 중인 Ollama에 연결만 한다(옵트인).
  `OLLAMA_MODEL` 환경변수가 없으면 기능 자체가 비활성화된다(조용히 기본 모델을 추측하지 않는다).
- 조용한 실패 금지: LLM 응답 파싱 실패는 "알 수 없음" 처리, 전체 요청은 죽지 않는다. Ollama 연결
  실패는 명확한 503 + 한국어 안내 메시지.
- 프론트엔드 검증은 `tsc --noEmit` + `npm run lint`(oxlint) + `npm run build` — 이 레포는 React
  컴포넌트/스토어 자동 테스트 인프라가 없다(기존 관례, `docs/superpowers/specs/2026-08-09-keylens-env-package-design.md` 참고). 새로 만들지 않는다.
- 백엔드 OCR 테스트는 `docs/demo/*.png`(전부 더미 값) 실제 이미지로 검증하고, 한국어 인식 모델이
  로컬에 벤더링돼 있지 않으면 스킵한다(`backend/tests/test_ocr_demo_screenshots.py`의 기존 관례
  그대로 — CI는 벤더링 후 pytest를 돌리므로 CI에서는 실제로 실행됨).

---

### Task 1: OCR 줄 단위 박스 좌표 보존

**Files:**
- Modify: `backend/app/ocr.py`
- Test: `backend/tests/test_ocr.py`(신규)

**Interfaces:**
- Consumes: 없음(기존 `_get_engine()`/`_line_key()`/`_NOISE_LINES` 재사용)
- Produces: `run_ocr_lines(image_bytes: bytes) -> list[dict]` — 각 dict는
  `{"text": str, "box": list[list[float]]}`(box는 4점 폴리곤 `[[x,y],[x,y],[x,y],[x,y]]`),
  줄 순서(위→아래, 왼→오)·노이즈 필터링은 기존 `run_ocr()`와 동일. 기존 `run_ocr(image_bytes) -> str`
  의 동작·시그니처는 변경 없음(리팩터링만, 회귀 없어야 함).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_ocr.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""OCR 줄 단위 박스 좌표 보존(화면 설명 기능용) — 실제 데모 스크린샷으로 검증.

한국어 인식 모델이 로컬에 벤더링돼 있지 않으면 스킵한다
(test_ocr_demo_screenshots.py 와 동일 관례 — CI는 벤더링 후 실행하므로 실제로 돈다).
"""
from pathlib import Path

import pytest

from app.ocr import _KOREAN_REC_MODEL, run_ocr, run_ocr_lines

DEMO_DIR = Path(__file__).parent.parent.parent / "docs" / "demo"

pytestmark = pytest.mark.skipif(
    not _KOREAN_REC_MODEL.exists(),
    reason="OCR 모델 미벤더링 — python backend/scripts/vendor_ocr_models.py 먼저 실행",
)


def test_run_ocr_lines_returns_text_and_box_per_line():
    image_bytes = (DEMO_DIR / "notion.png").read_bytes()
    lines = run_ocr_lines(image_bytes)
    assert len(lines) > 0
    for line in lines:
        assert isinstance(line["text"], str) and line["text"]
        assert len(line["box"]) == 4  # 4점 폴리곤
        for point in line["box"]:
            assert len(point) == 2
            x, y = point
            assert isinstance(x, float) and isinstance(y, float)
            assert x >= 0 and y >= 0


def test_run_ocr_lines_filters_noise_words():
    image_bytes = (DEMO_DIR / "notion.png").read_bytes()
    lines = run_ocr_lines(image_bytes)
    texts_lower = {line["text"].strip().lower() for line in lines}
    assert not (texts_lower & {"copy", "복사", "show", "표시"})


def test_run_ocr_lines_matches_run_ocr_joined_text():
    """리팩터링 회귀 확인 — run_ocr()의 줄바꿈 조인 결과와 정확히 같아야 한다."""
    image_bytes = (DEMO_DIR / "notion.png").read_bytes()
    joined = run_ocr(image_bytes)
    lines = run_ocr_lines(image_bytes)
    assert joined == "\n".join(line["text"] for line in lines)


def test_run_ocr_lines_empty_image_like_input_returns_empty_list():
    """1x1 흰 픽셀 PNG(텍스트 없음) — 빈 리스트를 반환해야 한다(예외 없이)."""
    import base64

    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    assert run_ocr_lines(tiny_png) == []
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run (`backend/`에서, OCR 모델이 벤더링돼 있어야 스킵되지 않고 실제 실패를 볼 수 있음 —
아직 벤더링 안 했다면 `python scripts/vendor_ocr_models.py` 먼저 실행):
`python -m pytest tests/test_ocr.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_ocr_lines' from 'app.ocr'`

- [ ] **Step 3: `ocr.py` 리팩터링 — 공통 헬퍼 추출 + `run_ocr_lines()` 추가**

`backend/app/ocr.py`의 `run_ocr` 함수 전체(69-85줄)를 다음으로 교체:
```python
def _recognize_lines(image_bytes: bytes) -> list[tuple[list, str]]:
    """이미지 → (박스, 텍스트) 줄 목록. 위→아래, 왼→오 정렬, 노이즈 줄 제외."""
    engine = _get_engine()
    result = engine(image_bytes)
    if result is None or result.boxes is None or len(result.boxes) == 0:
        return []

    rows = sorted(zip(result.boxes, result.txts), key=lambda r: _line_key(r[0]))

    lines: list[tuple[list, str]] = []
    for box, txt in rows:
        t = txt.strip()
        if not t or t.lower() in _NOISE_LINES:
            continue
        lines.append((box, t))
    return lines


def run_ocr(image_bytes: bytes) -> str:
    """이미지 바이트 → 줄 순서 보존 텍스트. 검출 결과가 없으면 빈 문자열."""
    lines = _recognize_lines(image_bytes)
    return "\n".join(t for _box, t in lines)


def run_ocr_lines(image_bytes: bytes) -> list[dict]:
    """이미지 바이트 → 줄 단위 {text, box} 목록(화면 설명 기능용 — 박스 좌표 보존).

    box는 4점 폴리곤 [[x,y],[x,y],[x,y],[x,y]](RapidOCR 원본 좌표, 이미지 픽셀 단위).
    """
    lines = _recognize_lines(image_bytes)
    return [
        {"text": t, "box": [[float(x), float(y)] for x, y in box]}
        for box, t in lines
    ]
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_ocr.py -v`
Expected: PASS(4개 전부, 벤더링 안 됐으면 SKIPPED 4개)

Run(회귀 확인): `python -m pytest tests/test_ocr_demo_screenshots.py -v`
Expected: 기존 8개 테스트 그대로 PASS(리팩터링이 `run_ocr()` 동작을 안 바꿨는지 확인)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/ocr.py backend/tests/test_ocr.py
git commit -m "$(cat <<'EOF'
feat(ocr): 줄 단위 박스 좌표 보존(run_ocr_lines) — 화면 설명 기능용

기존 run_ocr()이 버리던 박스 좌표를 공통 헬퍼(_recognize_lines)로
추출해 재사용. run_ocr()의 기존 동작(줄바꿈 조인 텍스트)은 변경 없음
— 기존 데모 스크린샷 회귀 테스트로 확인.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: 로컬 Ollama HTTP 클라이언트

**Files:**
- Create: `backend/app/ollama_client.py`
- Test: `backend/tests/test_ollama_client.py`

**Interfaces:**
- Consumes: 없음(독립 모듈, 표준 라이브러리만)
- Produces: `OllamaUnavailableError(RuntimeError)`. `OllamaConfig(base_url: str, model: str)`.
  `OllamaConfig.from_env(env: dict[str, str] | None = None) -> OllamaConfig | None`(`OLLAMA_MODEL`
  이 없으면 `None` — 기능 비활성 신호). `is_available(config: OllamaConfig, timeout: float = 2.0) -> bool`.
  `generate(config: OllamaConfig, prompt: str, timeout: float = 30.0) -> str`(실패 시
  `OllamaUnavailableError`).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_ollama_client.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Ollama HTTP 클라이언트 — urllib.request.urlopen을 monkeypatch해 실제 네트워크 없이 검증."""
import io
import json
import urllib.error

import pytest

from app.ollama_client import OllamaConfig, OllamaUnavailableError, generate, is_available

CONFIG = OllamaConfig(base_url="http://localhost:11434", model="llama3.2")


def test_config_from_env_reads_model_and_base_url():
    config = OllamaConfig.from_env({"OLLAMA_MODEL": "qwen2.5", "OLLAMA_BASE_URL": "http://x:1234"})
    assert config is not None
    assert config.model == "qwen2.5" and config.base_url == "http://x:1234"


def test_config_from_env_uses_default_base_url():
    config = OllamaConfig.from_env({"OLLAMA_MODEL": "qwen2.5"})
    assert config is not None
    assert config.base_url == "http://localhost:11434"


def test_config_from_env_missing_model_returns_none():
    """OLLAMA_MODEL이 없으면 기능 자체가 비활성 — 기본 모델을 조용히 추측하지 않는다."""
    assert OllamaConfig.from_env({}) is None


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._buf = io.BytesIO(payload)

    def read(self):
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_is_available_true_when_urlopen_succeeds(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(b"{}")
    )
    assert is_available(CONFIG) is True


def test_is_available_false_on_connection_error(monkeypatch):
    def raise_error(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", raise_error)
    assert is_available(CONFIG) is False


def test_generate_returns_response_text(monkeypatch):
    payload = json.dumps({"response": "이건 API 키입니다"}).encode("utf-8")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(payload)
    )
    assert generate(CONFIG, "설명해줘") == "이건 API 키입니다"


def test_generate_raises_on_connection_error(monkeypatch):
    def raise_error(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", raise_error)
    with pytest.raises(OllamaUnavailableError):
        generate(CONFIG, "설명해줘")


def test_generate_raises_on_malformed_response(monkeypatch):
    payload = json.dumps({"unexpected": "shape"}).encode("utf-8")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(payload)
    )
    with pytest.raises(OllamaUnavailableError):
        generate(CONFIG, "설명해줘")
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_ollama_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ollama_client'`

- [ ] **Step 3: `ollama_client.py` 구현**

`backend/app/ollama_client.py`:
```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_ollama_client.py -v`
Expected: PASS(8개 전부)

- [ ] **Step 5: 커밋**

```bash
git add backend/app/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "$(cat <<'EOF'
feat(explain): 로컬 Ollama HTTP 클라이언트(urllib만 사용)

OLLAMA_MODEL 환경변수 없으면 OllamaConfig.from_env()가 None을 반환해
기능을 비활성화한다 — 기본 모델을 조용히 추측하지 않음. 새 런타임
의존성 0.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 설명 파이프라인 (`explain.py`) — 지식베이스 대조 + Ollama 추론

**Files:**
- Modify: `backend/app/models.py`(끝에 새 섹션 추가)
- Create: `backend/app/explain.py`
- Test: `backend/tests/test_explain.py`

**Interfaces:**
- Consumes: `run_ocr_lines`(Task 1), `OllamaConfig`/`generate`/`OllamaUnavailableError`(Task 2),
  `KnowledgeBase.find(service, kind)`(기존), `analyze(AnalyzeRequest, kb)`(기존,
  `backend/app/classify/pipeline.py`).
- Produces: `models.py`에 `ExplainBox(BaseModel)`(`x,y,w,h: float`, `text: str`, `label: str`,
  `tier: Literal["known","ai_verified","ai_unverified"]`, `docs_url: Optional[str]`),
  `ExplainImageResponse(BaseModel)`(`boxes: list[ExplainBox]`), `ExplainStatusResponse(BaseModel)`
  (`available: bool`). `explain.py`에 `explain_image(image_bytes: bytes, kb: KnowledgeBase,
  config: OllamaConfig) -> list[ExplainBox]`.

- [ ] **Step 1: `models.py`에 응답 스키마 추가**

`backend/app/models.py` 맨 끝(273번째 줄, `SdkPendingRequest` 클래스 뒤)에 추가:
```python


# ── 화면 설명(EXPLAIN, 1단계: 지식베이스 대조 + 로컬 Ollama) ──


class ExplainBox(BaseModel):
    """스크린샷 한 줄에 대한 설명 — 좌표(원본 이미지 픽셀 단위)와 등급."""

    x: float
    y: float
    w: float
    h: float
    text: str
    label: str
    tier: Literal["known", "ai_verified", "ai_unverified"]
    docs_url: Optional[str] = None


class ExplainImageResponse(BaseModel):
    boxes: list[ExplainBox]


class ExplainStatusResponse(BaseModel):
    """Ollama 가용 여부 — 프론트가 '이 화면 설명해줘' 버튼 표시 여부를 판단하는 데 씀."""

    available: bool
```

- [ ] **Step 2: 실패하는 테스트 작성**

`backend/tests/test_explain.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""설명 파이프라인 — 지식베이스 대조 + Ollama 추론(1단계, 검색 없음).

실제 이미지는 docs/demo/notion.png(더미 값)를 쓰되, Ollama 호출은 monkeypatch로 대체해
로컬 Ollama 없이도 CI에서 돈다. 한국어 인식 모델이 벤더링돼 있지 않으면 스킵.
"""
import json
from pathlib import Path

import pytest

from app import explain, ollama_client
from app.knowledge import load_knowledge_base
from app.ocr import _KOREAN_REC_MODEL
from app.ollama_client import OllamaConfig, OllamaUnavailableError

DEMO_DIR = Path(__file__).parent.parent.parent / "docs" / "demo"

pytestmark = pytest.mark.skipif(
    not _KOREAN_REC_MODEL.exists(),
    reason="OCR 모델 미벤더링 — python backend/scripts/vendor_ocr_models.py 먼저 실행",
)

CONFIG = OllamaConfig(base_url="http://localhost:11434", model="llama3.2")


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


@pytest.fixture
def notion_image():
    return (DEMO_DIR / "notion.png").read_bytes()


def test_known_service_line_gets_docs_url_without_calling_ollama(kb, notion_image, monkeypatch):
    """지식베이스에 있는 서비스(Notion API 키)는 Ollama를 호출하지 않고도 known으로 라벨링된다."""
    called = []
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **kw: called.append(1) or "[]")

    boxes = explain.explain_image(notion_image, kb, CONFIG)

    known = [b for b in boxes if b.tier == "known"]
    assert any(b.label and b.docs_url for b in known), "known 박스 중 docs_url이 채워진 게 없음"
    # Notion API 키 값이 포함된 줄은 known이어야 하고, 이 케이스에선 미분류 줄이 없을 수도 있으므로
    # Ollama가 아예 호출 안 됐거나(미분류 줄 없음) 한 번만 호출됐는지만 확인(과호출 방지).
    assert len(called) <= 1


def test_unknown_line_gets_ai_label_from_ollama(kb, notion_image, monkeypatch):
    def fake_generate(config, prompt, timeout=30.0):
        assert "index" in prompt  # 프롬프트가 JSON 형식 안내를 포함하는지 최소 확인
        return json.dumps([{"index": 0, "label": "안내 문구"}])

    monkeypatch.setattr(ollama_client, "generate", fake_generate)

    boxes = explain.explain_image(notion_image, kb, CONFIG)

    ai_boxes = [b for b in boxes if b.tier == "ai_unverified"]
    # 최소 하나는 실제로 Ollama가 붙여준 라벨("안내 문구")을 갖고 있어야 한다(전부 "알 수 없음"이면 실패).
    assert any(b.label == "안내 문구" for b in ai_boxes) or not ai_boxes


def test_ollama_unavailable_falls_back_to_unknown_label(kb, notion_image, monkeypatch):
    """Ollama 연결 실패 시 전체 요청은 안 죽고, 미분류 줄은 '알 수 없음'으로 표시된다."""
    def raise_unavailable(config, prompt, timeout=30.0):
        raise OllamaUnavailableError("연결 실패")

    monkeypatch.setattr(ollama_client, "generate", raise_unavailable)

    boxes = explain.explain_image(notion_image, kb, CONFIG)

    ai_boxes = [b for b in boxes if b.tier == "ai_unverified"]
    assert all(b.label == "알 수 없음" for b in ai_boxes)


def test_malformed_ollama_json_falls_back_gracefully(kb, notion_image, monkeypatch):
    """Ollama가 JSON이 아닌 잡담을 반환해도 전체 요청은 실패하지 않는다."""
    monkeypatch.setattr(
        ollama_client, "generate", lambda *a, **kw: "죄송하지만 잘 모르겠어요!"
    )

    boxes = explain.explain_image(notion_image, kb, CONFIG)

    ai_boxes = [b for b in boxes if b.tier == "ai_unverified"]
    assert all(b.label == "알 수 없음" for b in ai_boxes)


def test_all_boxes_have_valid_rect_coordinates(kb, notion_image, monkeypatch):
    monkeypatch.setattr(ollama_client, "generate", lambda *a, **kw: "[]")
    boxes = explain.explain_image(notion_image, kb, CONFIG)
    assert len(boxes) > 0
    for b in boxes:
        assert b.w > 0 and b.h > 0
        assert b.x >= 0 and b.y >= 0
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_explain.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.explain'`

- [ ] **Step 4: `explain.py` 구현**

`backend/app/explain.py`:
```python
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
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_explain.py -v`
Expected: PASS(5개 전부, 벤더링 안 됐으면 SKIPPED 5개)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/models.py backend/app/explain.py backend/tests/test_explain.py
git commit -m "$(cat <<'EOF'
feat(explain): 지식베이스 대조 + 로컬 Ollama 추론 파이프라인

지식베이스에 있는 줄은 Ollama 호출 없이 즉시 라벨링(known), 없는
줄만 배치로 Ollama에 물어봄. 연결 실패·JSON 파싱 실패는 전부
"알 수 없음"으로 안전하게 폴백(전체 요청 실패 없음).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: FastAPI 엔드포인트 + `.env.example`

**Files:**
- Modify: `backend/app/main.py`
- Modify: `.env.example`
- Test: `backend/tests/test_explain_api.py`

**Interfaces:**
- Consumes: `explain_image`(Task 3), `OllamaConfig.from_env`/`is_available`(Task 2).
- Produces: 모듈 전역 `OLLAMA_CONFIG: OllamaConfig | None`. 라우트 함수 `explain_status() ->
  ExplainStatusResponse`, `async def explain_image_endpoint(image: UploadFile) -> ExplainImageResponse`.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_explain_api.py`:
```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""설명 기능 엔드포인트 — httpx(certifi/MPL) 회피, 라우트 함수 직접 호출.

explain_image_endpoint 는 async def 라 asyncio.run()으로 직접 실행한다(pytest-asyncio 같은
새 테스트 의존성 추가 없이 — manager-relay/tests/test_main.py 의 raw ASGI 호출 테스트와 같은
정신: 표준 라이브러리만으로 async 코드를 동기 테스트에서 구동한다).
"""
import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from app import main
from app.ocr import _KOREAN_REC_MODEL
from app.ollama_client import OllamaConfig

DEMO_DIR = Path(__file__).parent.parent.parent / "docs" / "demo"

pytestmark = pytest.mark.skipif(
    not _KOREAN_REC_MODEL.exists(),
    reason="OCR 모델 미벤더링 — python backend/scripts/vendor_ocr_models.py 먼저 실행",
)


def test_status_unavailable_when_ollama_config_none(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", None)
    result = main.explain_status()
    assert result.available is False


def test_status_reflects_health_check(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", OllamaConfig("http://x", "m"))
    monkeypatch.setattr(main.ollama_client, "is_available", lambda config: True)
    assert main.explain_status().available is True

    monkeypatch.setattr(main.ollama_client, "is_available", lambda config: False)
    assert main.explain_status().available is False


class _FakeUploadFile:
    def __init__(self, content_type: str, data: bytes):
        self.content_type = content_type
        self._data = data

    async def read(self, max_bytes: int) -> bytes:
        return self._data[:max_bytes]


def test_explain_image_endpoint_503_when_not_configured(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", None)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(main.explain_image_endpoint(image=_FakeUploadFile("image/png", b"fake")))
    assert exc_info.value.status_code == 503


def test_explain_image_endpoint_422_on_non_image(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", OllamaConfig("http://x", "m"))
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(main.explain_image_endpoint(image=_FakeUploadFile("text/plain", b"fake")))
    assert exc_info.value.status_code == 422


def test_explain_image_endpoint_returns_boxes(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_CONFIG", OllamaConfig("http://x", "m"))
    monkeypatch.setattr(main.ollama_client, "generate", lambda *a, **kw: "[]")
    image_bytes = (DEMO_DIR / "notion.png").read_bytes()
    result = asyncio.run(
        main.explain_image_endpoint(image=_FakeUploadFile("image/png", image_bytes))
    )
    assert len(result.boxes) > 0
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_explain_api.py -v`
Expected: FAIL — `AttributeError: module 'app.main' has no attribute 'OLLAMA_CONFIG'`(또는 유사)

- [ ] **Step 3: `main.py`에 엔드포인트 추가**

`backend/app/main.py` 상단 import 블록에 추가(`from .ocr import OcrUnavailableError, run_ocr` 다음 줄):
```python
from . import explain, ollama_client
from .models import (
    ...  # 기존 import에 아래 3개 추가
    ExplainImageResponse,
    ExplainStatusResponse,
)
from .ollama_client import OllamaConfig
```
(정확히는 기존 `from .models import (...)` 블록의 알파벳 순서 안에 `ExplainImageResponse`,
`ExplainStatusResponse`를 끼워 넣는다.)

`_MAX_IMAGE_BYTES` 상수 정의 다음, `@app.post("/analyze/image", ...)` 엔드포인트 아래에 추가:
```python
# ── 화면 설명(EXPLAIN, 1단계) ──
# 로컬 Ollama가 없거나 OLLAMA_MODEL이 설정 안 됐으면 기능 자체가 비활성(None) — 앱은 어떤
# 모델도 번들하지 않는다. 설계 근거: docs/superpowers/specs/2026-08-27-screenshot-explain-design.md

OLLAMA_CONFIG = OllamaConfig.from_env()


@app.get("/explain/status", response_model=ExplainStatusResponse)
def explain_status() -> ExplainStatusResponse:
    available = OLLAMA_CONFIG is not None and ollama_client.is_available(OLLAMA_CONFIG)
    return ExplainStatusResponse(available=available)


@app.post("/explain/image", response_model=ExplainImageResponse)
async def explain_image_endpoint(image: UploadFile = File(...)) -> ExplainImageResponse:
    if OLLAMA_CONFIG is None:
        raise HTTPException(
            status_code=503,
            detail="화면 설명 기능이 설정되지 않았어요 — OLLAMA_MODEL 환경변수를 설정하세요",
        )
    if image.content_type is None or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="이미지 파일만 업로드할 수 있어요")

    data = await image.read(_MAX_IMAGE_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="빈 파일이에요")
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="이미지가 너무 커요(15MB 제한)")

    try:
        boxes = explain.explain_image(data, KB, OLLAMA_CONFIG)
    except OcrUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
    return ExplainImageResponse(boxes=boxes)
```

- [ ] **Step 4: `.env.example`에 안내 추가**

`.env.example`의 `# --- 백엔드 (VAULT-1/2, 구현 완료) ---` 섹션 앞에 추가:
```text

# --- 화면 설명 기능(EXPLAIN, 1단계 — 로컬 Ollama, 옵트인) ---
# OLLAMA_MODEL이 없으면 "이 화면 설명해줘" 기능 자체가 비활성화된다(기본 모델을 추측하지 않음).
# 앱은 어떤 모델도 번들하지 않는다 — 이미 설치·실행 중인 Ollama에만 연결한다.
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_explain_api.py -v`
Expected: PASS(5개 전부, 벤더링 안 됐으면 SKIPPED 5개)

Run(전체 회귀): `python -m pytest -v`
Expected: 기존 테스트 전부 그대로 PASS + 새 테스트들 PASS

- [ ] **Step 6: 커밋**

```bash
git add backend/app/main.py backend/tests/test_explain_api.py .env.example
git commit -m "$(cat <<'EOF'
feat(explain): /explain/status, /explain/image 엔드포인트

OLLAMA_MODEL 미설정 시 503 + 명확한 한국어 안내. .env.example에
옵트인 설정 안내 추가.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 프론트엔드 — "이 화면 설명해줘" 모달

**Files:**
- Modify: `frontend/src/api/types.ts`(ExplainBox 인터페이스 추가)
- Modify: `frontend/src/api/client.ts`(explainStatusApi, explainImageApi 추가)
- Create: `frontend/src/components/modals/ExplainModal.tsx`
- Modify: `frontend/src/store/keylensStore.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/screens/InputScreen.tsx`

**Interfaces:**
- Consumes: `POST /explain/image`, `GET /explain/status`(Task 4). `vault 잠금과 무관 — 별도 인증
  불필요(비밀 값을 다루지 않음, 화면 설명은 메타데이터/라벨만)`.
- Produces: `ExplainBox` 타입(`types.ts`), `explainStatusApi(): Promise<boolean>`,
  `explainImageApi(image: Blob): Promise<ExplainBox[]>`(`client.ts`). 스토어에
  `explainAvailable: boolean`, `explainOpen: boolean`, `explainLoading: boolean`,
  `explainBoxes: ExplainBox[]`, `checkExplainAvailable(): Promise<void>`,
  `openExplain(): Promise<void>`, `closeExplain(): void`.

- [ ] **Step 1: `types.ts`에 `ExplainBox` 추가**

`frontend/src/api/types.ts`의 `VaultImportResult` 인터페이스 뒤에 추가:
```typescript
/** 화면 설명 기능(1단계) 결과 한 항목 — 좌표는 원본 이미지 픽셀 단위. */
export interface ExplainBox {
  x: number
  y: number
  w: number
  h: number
  text: string
  label: string
  tier: 'known' | 'ai_verified' | 'ai_unverified'
  docs_url?: string
}
```

- [ ] **Step 2: `client.ts`에 API 함수 추가**

`frontend/src/api/client.ts` 상단 import에 `ExplainBox` 추가(`VaultVerifyResult,` 다음 줄):
```typescript
  ExplainBox,
```
파일 끝(`sdkApi` 객체 뒤)에 추가:
```typescript

// ── 화면 설명(EXPLAIN, 1단계) ──

export async function explainStatusApi(timeoutMs = 3000): Promise<boolean> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE}/explain/status`, { signal: ctrl.signal })
    if (!res.ok) return false
    const body = (await res.json()) as { available: boolean }
    return body.available
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

/** POST /explain/image — 로컬 LLM 추론이 걸릴 수 있어 타임아웃을 넉넉히 잡는다. */
export async function explainImageApi(image: Blob, timeoutMs = 45000): Promise<ExplainBox[]> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const form = new FormData()
    form.append('image', image, 'screenshot.png')
    const res = await fetch(`${API_BASE}/explain/image`, {
      method: 'POST',
      body: form,
      signal: ctrl.signal,
    })
    if (!res.ok) {
      if (res.status === 503) {
        throw new ApiError('화면 설명 기능을 쓸 수 없어요 — Ollama가 실행 중인지 확인하세요')
      }
      if (res.status === 422) {
        throw new ApiError('이미지를 읽지 못했어요 — 다른 스크린샷으로 시도해 주세요')
      }
      throw new ApiError(`문제가 발생했어요 (오류 ${res.status}) — 잠시 후 다시 시도해 보세요.`)
    }
    const body = (await res.json()) as { boxes: ExplainBox[] }
    return body.boxes
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('응답이 너무 늦어요 — 다시 시도해 보세요.')
    }
    throw new ApiError('KeyLens에 연결할 수 없어요 — 잠시 후 다시 시도하거나 재시작해 보세요.')
  } finally {
    clearTimeout(timer)
  }
}
```

- [ ] **Step 3: 스토어에 상태·액션 추가**

`frontend/src/store/keylensStore.ts`의 현재 import 블록(9-17번째 줄)을 다음으로 교체:
```typescript
import {
  analyzeApi,
  analyzeImageApi,
  ApiError,
  explainImageApi,
  explainStatusApi,
  fetchKnowledge,
  sdkApi,
  vaultApi,
  VaultApiError,
} from '@/api/client'
import type { ExplainBox } from '@/api/types'
```
(새 `import type { ExplainBox } from '@/api/types'` 줄은 기존 `} from '@/api/client'` 다음,
`import { metaToVaultItem, ... } from '@/api/map'` 줄 앞에 추가한다.)

`attachedImage: string | null` 선언(101번째 줄 부근) 뒤에 상태 필드 추가:
```typescript
  /** 화면 설명 기능(1단계) — Ollama 가용 여부(부팅 시 1회 확인). */
  explainAvailable: boolean
  explainOpen: boolean
  explainLoading: boolean
  explainBoxes: ExplainBox[]
```
(`ExplainBox` 타입은 파일 상단 `import type { ... } from '@/api/types'` 블록에 추가)

액션 타입 선언 블록(`resetProto: () => void` 앞)에 추가:
```typescript
  /** 화면 설명(1단계, 검색·캐시 없음). */
  checkExplainAvailable: () => Promise<void>
  openExplain: () => Promise<void>
  closeExplain: () => void
```

초기 state(`attachedImage: null,` 뒤)에 추가:
```typescript
    explainAvailable: false,
    explainOpen: false,
    explainLoading: false,
    explainBoxes: [],
```

`boot: async () => {` 함수 본문 안, `get().loadPending()` 호출 다음 줄에 추가(await 없이 —
부팅을 막지 않는 보조 상태 확인):
```typescript
      get().checkExplainAvailable()
```

액션 구현은 `importVault` 정의 뒤, `resetProto` 앞에 추가:
```typescript
    // ── 화면 설명(EXPLAIN, 1단계) ──
    checkExplainAvailable: async () => {
      const available = await explainStatusApi()
      set({ explainAvailable: available })
    },
    openExplain: async () => {
      const img = get().analyzedImage
      if (!img || img === 'sample') {
        get().showToast('실제 스크린샷이 있을 때만 화면 설명을 볼 수 있어요')
        return
      }
      set({ explainOpen: true, explainLoading: true, explainBoxes: [] })
      try {
        const blob = await (await fetch(img)).blob()
        const boxes = await explainImageApi(blob)
        set({ explainLoading: false, explainBoxes: boxes })
      } catch (e) {
        set({ explainLoading: false, explainOpen: false })
        get().showToast(e instanceof ApiError ? e.message : '화면 설명을 불러오지 못했어요')
      }
    },
    closeExplain: () => set({ explainOpen: false, explainBoxes: [] }),
```

- [ ] **Step 4: `ExplainModal` 컴포넌트 작성**

`frontend/src/components/modals/ExplainModal.tsx`(신규):
```typescript
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { useKeylens } from '@/store/keylensStore'

const TIER_STYLE: Record<string, { border: string; bg: string; badge: string }> = {
  known: { border: '2px solid #3ECF8E', bg: 'rgba(62,207,142,.08)', badge: '분류됨' },
  ai_verified: { border: '2px dashed #E3B341', bg: 'rgba(227,179,65,.08)', badge: 'AI 추정(확인)' },
  ai_unverified: { border: '2px dashed #6B7280', bg: 'rgba(107,114,128,.08)', badge: 'AI 추정' },
}

/** "이 화면 설명해줘" 결과 모달(1단계) — 스크린샷 원본 비율 위에 박스+라벨 오버레이. */
export function ExplainModal() {
  const open = useKeylens((s) => s.explainOpen)
  const loading = useKeylens((s) => s.explainLoading)
  const boxes = useKeylens((s) => s.explainBoxes)
  const image = useKeylens((s) => s.analyzedImage)
  const close = useKeylens((s) => s.closeExplain)
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null)

  return (
    <Modal open={open} onClose={close} title="이 화면 설명" className="w-[720px] max-w-[94vw]">
      <div className="text-[15px] font-bold">이 화면 설명</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        초록 실선은 이미 아는 서비스, 회색/노랑 점선은 AI 추정이에요 — AI 추정은 틀릴 수 있습니다.
      </p>
      {loading && (
        <div className="mt-4 py-8 text-center text-[13px] text-muted">로컬 LLM이 분석 중…</div>
      )}
      {!loading && image && image !== 'sample' && (
        <div className="relative mt-3 inline-block max-w-full">
          <img
            src={image}
            alt="분석한 스크린샷"
            className="block max-h-[70vh] max-w-full rounded-lg"
            onLoad={(e) => {
              const el = e.currentTarget
              setNaturalSize({ w: el.naturalWidth, h: el.naturalHeight })
            }}
          />
          {naturalSize &&
            boxes.map((b, i) => {
              const style = TIER_STYLE[b.tier] ?? TIER_STYLE.ai_unverified
              return (
                <div
                  key={i}
                  title={`${b.text} → ${b.label}`}
                  className="absolute rounded-[2px]"
                  style={{
                    left: `${(b.x / naturalSize.w) * 100}%`,
                    top: `${(b.y / naturalSize.h) * 100}%`,
                    width: `${(b.w / naturalSize.w) * 100}%`,
                    height: `${(b.h / naturalSize.h) * 100}%`,
                    border: style.border,
                    background: style.bg,
                  }}
                >
                  <span
                    className="absolute -top-[18px] left-0 whitespace-nowrap rounded-[3px] px-[4px] text-[10px] font-semibold text-white"
                    style={{ background: style.border.split(' ')[2] }}
                  >
                    {b.label}
                  </span>
                </div>
              )
            })}
        </div>
      )}
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={close}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          닫기
        </button>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 5: `App.tsx`에 모달 연결**

`frontend/src/App.tsx:19`(`import { DeleteModal, DupModal, EmailSyncModal, EnvModal, RotateModal,
SyncModal } from '@/components/modals/Modals'`) 바로 다음 줄에 새 import 추가(`ExplainModal`은
`Modals.tsx`가 아니라 별도 파일이므로 별도 import 문이 필요하다):
```typescript
import { ExplainModal } from '@/components/modals/ExplainModal'
```
`frontend/src/App.tsx:95`(`<EmailSyncModal />`) 다음 줄에 추가:
```tsx
      <ExplainModal />
```

- [ ] **Step 6: `InputScreen.tsx`에 버튼 추가**

결과 헤더 버튼 줄(`onClick={s.saveAll}` 버튼 다음, `</div>` 닫기 전)에 추가:
```tsx
            {s.explainAvailable && hasRealImg && (
              <button
                type="button"
                onClick={s.openExplain}
                title="화면 각 영역이 뭘 의미하는지 박스로 설명(로컬 LLM 필요)"
                className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[7px] text-[12px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
              >
                이 화면 설명해줘
              </button>
            )}
```
(`s.explainAvailable`는 이미 `const s = useKeylens()`로 구조분해 안 하고 `s.` 접두어로 쓴다 —
이 컴포넌트 상단에서 `const { ..., attachedImage, ... } = s`로 구조분해하는 기존 목록에
`explainAvailable`을 추가하지 않아도 `s.explainAvailable`로 직접 접근 가능하니 편한 쪽으로 통일할 것.)

- [ ] **Step 7: 타입체크·린트·빌드 검증**

Run(`frontend/`에서):
```bash
npx tsc --noEmit
npm run lint
npm run build
```
Expected: 셋 다 에러 없이 통과.

- [ ] **Step 8: 수동 브라우저 확인**

1. `backend/.env`에 `OLLAMA_MODEL=`(비워둠)인 채로 백엔드 기동 → 프론트에서 스크린샷 분석 후
   "이 화면 설명해줘" 버튼이 안 보이는지 확인(기능 비활성).
2. 실제 Ollama를 설치·실행하고(`ollama pull llama3.2` 등) `OLLAMA_MODEL=llama3.2`로 설정 후
   백엔드 재기동 → 버튼이 보이는지, 클릭 시 모달이 열리고 로딩 후 박스가 그려지는지 확인.
3. `docs/demo/notion.png` 같은 데모 스크린샷으로 시도해 known(초록)/AI 추정(회색 점선) 박스가
   구분되어 보이는지 확인.

- [ ] **Step 9: 커밋**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts \
  frontend/src/components/modals/ExplainModal.tsx frontend/src/store/keylensStore.ts \
  frontend/src/App.tsx frontend/src/components/screens/InputScreen.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): "이 화면 설명해줘" 모달(1단계, 검색·캐시 없음)

OLLAMA_MODEL 미설정 시 버튼 자체가 안 보임. 스크린샷 원본 위에
분류됨(초록 실선)/AI 추정(점선) 박스를 백분율 좌표로 오버레이.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```
