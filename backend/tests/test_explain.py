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


def _synthetic_lines(n: int) -> list[dict]:
    """실제 OCR 없이 미분류 줄 개수를 정확히 통제하기 위한 합성 줄 목록(run_ocr_lines 대체용)."""
    return [
        {"text": f"unknown line {i}", "box": [[0, i * 10], [10, i * 10], [10, i * 10 + 10], [0, i * 10 + 10]]}
        for i in range(n)
    ]


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


def test_ollama_connection_failure_propagates_as_exception(kb, notion_image, monkeypatch):
    """Ollama 연결 실패는 '알 수 없음'으로 조용히 낮추지 않고 그대로 위로 전파돼야 한다 —

    연결 자체가 안 되는 것(사용자가 알아야 할 문제, main.py에서 503으로 변환됨)과 응답은
    받았지만 내용이 JSON이 아닌 것(_parse_labels가 처리하는 별개의 정상적인 저하 경로)은
    설계상 구분되는 실패 모드라서다.
    """
    def raise_unavailable(config, prompt, timeout=30.0):
        raise OllamaUnavailableError("연결 실패")

    monkeypatch.setattr(ollama_client, "generate", raise_unavailable)

    with pytest.raises(OllamaUnavailableError):
        explain.explain_image(notion_image, kb, CONFIG)


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


def test_guessed_service_that_looks_like_secret_skips_tavily(kb, notion_image, monkeypatch, tmp_path):
    """Ollama가 서비스명 대신 값처럼 보이는 문자열(예: API 키 일부)을 추측해도 Tavily로 보내지
    않는다 — 시크릿이 제3자 검색 쿼리로 새어나가는 걸 막는다(discoveries_repo 값-토큰 휴리스틱 재사용)."""
    from app import discoveries_repo, tavily_client

    monkeypatch.setattr(
        ollama_client, "generate",
        lambda *a, **kw: json.dumps(
            [{"index": 0, "label": "안내 문구", "guessed_service": "sk-proj-AbCdEfGh12345678"}]
        ),
    )
    search_calls = []
    monkeypatch.setattr(tavily_client, "search", lambda *a, **kw: search_calls.append(1) or [])
    monkeypatch.setattr(discoveries_repo, "find_by_pattern", lambda path, pattern: None)

    tavily_config = tavily_client.TavilyConfig(api_key="tvly-dummy")
    boxes = explain.explain_image(
        notion_image, kb, CONFIG, tavily_config=tavily_config,
        discoveries_path=tmp_path / "local_discoveries.yaml",
    )

    assert search_calls == []
    assert any(b.tier == "ai_unverified" and b.label == "안내 문구" for b in boxes)


def test_verification_capped_per_image(kb, monkeypatch, tmp_path):
    """검증 시도(Tavily 검색 + Ollama 2차 호출)가 이미지 1건당 상한(3건)을 넘지 않는다 — 넘는
    줄은 오류가 아니라 1차 추론 라벨(ai_unverified)로 남는다."""
    from app import discoveries_repo, tavily_client

    lines = _synthetic_lines(5)
    monkeypatch.setattr(explain, "run_ocr_lines", lambda image_bytes: lines)

    call_count = [0]

    def fake_generate(config, prompt, timeout=30.0):
        call_count[0] += 1
        if call_count[0] == 1:
            names = ["ServiceAlpha", "ServiceBeta", "ServiceGamma", "ServiceDelta", "ServiceEpsilon"]
            return json.dumps(
                [{"index": i, "label": f"안내{i}", "guessed_service": names[i]} for i in range(5)]
            )
        return json.dumps({"label": "확인됨", "docs_url": "https://example.com/docs"})

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    search_calls = []
    monkeypatch.setattr(
        tavily_client, "search",
        lambda config, query, **kw: search_calls.append(query)
        or [{"title": "t", "url": "https://example.com/docs", "content": "c"}],
    )
    monkeypatch.setattr(discoveries_repo, "find_by_pattern", lambda path, pattern: None)

    tavily_config = tavily_client.TavilyConfig(api_key="tvly-dummy")
    boxes = explain.explain_image(
        b"fake-image-bytes", kb, CONFIG, tavily_config=tavily_config,
        discoveries_path=tmp_path / "local_discoveries.yaml",
    )

    assert call_count[0] == 1 + 3  # 1차 추론 1회 + 검증 상한 3회
    assert len(search_calls) == 3
    verified = [b for b in boxes if b.tier == "ai_verified"]
    assert len(verified) == 3
    unverified = [b for b in boxes if b.tier == "ai_unverified"]
    assert len(unverified) == 2  # 상한 초과분은 1차 추론 라벨 그대로


def test_tavily_search_deduped_by_guessed_service(kb, monkeypatch, tmp_path):
    """같은 이미지 안에서 여러 줄이 같은 서비스명을 추측하면 Tavily 검색은 한 번만 호출한다."""
    from app import discoveries_repo, tavily_client

    lines = _synthetic_lines(2)
    monkeypatch.setattr(explain, "run_ocr_lines", lambda image_bytes: lines)

    call_count = [0]

    def fake_generate(config, prompt, timeout=30.0):
        call_count[0] += 1
        if call_count[0] == 1:
            return json.dumps(
                [
                    {"index": 0, "label": "안내0", "guessed_service": "SameService"},
                    {"index": 1, "label": "안내1", "guessed_service": "SameService"},
                ]
            )
        return json.dumps({"label": "확인됨", "docs_url": "https://example.com/docs"})

    monkeypatch.setattr(ollama_client, "generate", fake_generate)
    search_calls = []
    monkeypatch.setattr(
        tavily_client, "search",
        lambda config, query, **kw: search_calls.append(query)
        or [{"title": "t", "url": "https://example.com/docs", "content": "c"}],
    )
    monkeypatch.setattr(discoveries_repo, "find_by_pattern", lambda path, pattern: None)

    tavily_config = tavily_client.TavilyConfig(api_key="tvly-dummy")
    boxes = explain.explain_image(
        b"fake-image-bytes", kb, CONFIG, tavily_config=tavily_config,
        discoveries_path=tmp_path / "local_discoveries.yaml",
    )

    assert len(search_calls) == 1
    verified = [b for b in boxes if b.tier == "ai_verified"]
    assert len(verified) == 2
