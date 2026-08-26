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
