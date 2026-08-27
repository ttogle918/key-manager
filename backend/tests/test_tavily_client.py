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


def test_search_returns_empty_list_on_non_utf8_response(monkeypatch):
    """프록시/방화벽이 끼워 넣은 에러 페이지 등 UTF-8이 아닌 응답 본문도 예외 없이 빈 리스트."""
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(b"\xff\xfe\x00\x01")
    )
    assert search(CONFIG, "아무 쿼리") == []


def test_search_returns_empty_list_when_results_not_a_list(monkeypatch):
    payload = json.dumps({"results": "oops"}).encode("utf-8")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(payload)
    )
    assert search(CONFIG, "아무 쿼리") == []


def test_search_returns_empty_list_when_top_level_not_a_dict(monkeypatch):
    payload = json.dumps([1, 2, 3]).encode("utf-8")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(payload)
    )
    assert search(CONFIG, "아무 쿼리") == []


def test_search_skips_malformed_entries_in_results_list(monkeypatch):
    payload = json.dumps(
        {
            "results": [
                {"title": "정상 결과", "url": "https://example.com", "content": "..."},
                "이건 dict가 아님",
                {"title": "url 없음"},
                None,
            ]
        }
    ).encode("utf-8")
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=None: _FakeResponse(payload)
    )
    results = search(CONFIG, "아무 쿼리")
    assert results == [{"title": "정상 결과", "url": "https://example.com", "content": "..."}]
