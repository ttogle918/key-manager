# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""load_env() — config.py/client.py를 엮는 공개 API. 둘 다 monkeypatch로 대체해
네트워크·파일시스템 없이 조합 로직만 검증한다(실제 왕복 검증은 Task 5의 통합 테스트)."""
from pathlib import Path

import pytest

import keylens_env
from keylens_env.exceptions import KeylensLockedError


def test_load_env_uses_config_when_project_not_given(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path("/repo/blog")))
    captured = {}

    def fake_fetch_env(project, path, base_url):
        captured["args"] = (project, path, base_url)
        return {"OPENAI_API_KEY": "sk-dummy"}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    keylens_env.load_env()

    assert captured["args"][0] == "블로그"
    assert captured["args"][1] == str(Path("/repo/blog"))
    assert __import__("os").environ["OPENAI_API_KEY"] == "sk-dummy"


def test_load_env_explicit_project_skips_config(monkeypatch):
    def fail_if_called():
        raise AssertionError("project가 명시되면 find_config가 호출되면 안 됨")

    monkeypatch.setattr(keylens_env, "find_config", fail_if_called)
    captured = {}

    def fake_fetch_env(project, path, base_url):
        captured["project"] = project
        return {}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)

    keylens_env.load_env(project="사이드")

    assert captured["project"] == "사이드"


def test_load_env_propagates_typed_exception(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path(".")))

    def raise_locked(project, path, base_url):
        raise KeylensLockedError("잠김")

    monkeypatch.setattr(keylens_env, "fetch_env", raise_locked)

    with pytest.raises(KeylensLockedError):
        keylens_env.load_env()


def test_load_env_uses_env_var_base_url(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path(".")))
    monkeypatch.setenv("KEYLENS_BASE_URL", "http://127.0.0.1:9999")
    captured = {}

    def fake_fetch_env(project, path, base_url):
        captured["base_url"] = base_url
        return {}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)
    keylens_env.load_env()

    assert captured["base_url"] == "http://127.0.0.1:9999"


def test_load_env_defaults_base_url_when_env_var_unset(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path(".")))
    monkeypatch.delenv("KEYLENS_BASE_URL", raising=False)
    captured = {}

    def fake_fetch_env(project, path, base_url):
        captured["base_url"] = base_url
        return {}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)
    keylens_env.load_env()

    assert captured["base_url"] == keylens_env.client.DEFAULT_BASE_URL
