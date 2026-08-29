# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""load_env() - config.py/client.py를 엮는 공개 API. 둘 다 monkeypatch로 대체해
네트워크·파일시스템 없이 조합 로직만 검증한다(실제 왕복 검증은 통합 테스트).

주소(base_url) 결정은 이제 load_env가 아니라 client.resolve_base_url이 맡는다
(포트 자동 탐색이 들어가면서 옮겼다) - 그쪽 검증은 test_client_discovery.py 에 있다.
"""
import os
from pathlib import Path

import pytest

import keylens_env
from keylens_env.exceptions import KeylensEmptyCollectionError, KeylensLockedError


def test_load_env_uses_config_when_collection_not_given(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path("/repo/blog")))
    captured = {}

    def fake_fetch_env(collection, path):
        captured["args"] = (collection, path)
        return {"OPENAI_API_KEY": "sk-dummy"}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    injected = keylens_env.load_env()

    assert captured["args"] == ("블로그", str(Path("/repo/blog")))
    assert os.environ["OPENAI_API_KEY"] == "sk-dummy"
    assert injected == {"OPENAI_API_KEY": "sk-dummy"}


def test_load_env_explicit_collection_skips_config(monkeypatch):
    def fail_if_called():
        raise AssertionError("collection이 명시되면 find_config가 호출되면 안 됨")

    monkeypatch.setattr(keylens_env, "find_config", fail_if_called)
    captured = {}

    def fake_fetch_env(collection, path):
        captured["collection"] = collection
        return {"K": "v"}

    monkeypatch.setattr(keylens_env, "fetch_env", fake_fetch_env)
    monkeypatch.delenv("K", raising=False)

    keylens_env.load_env("사이드")

    assert captured["collection"] == "사이드"


def test_load_env_still_accepts_legacy_project_kwarg(monkeypatch):
    """옛 이름(project=)으로 쓰던 코드가 깨지지 않아야 한다."""
    monkeypatch.setattr(keylens_env, "fetch_env", lambda c, p: {"K": "v"})
    monkeypatch.delenv("K", raising=False)

    keylens_env.load_env(project="사이드")

    assert os.environ["K"] == "v"


def test_load_env_propagates_typed_exception(monkeypatch):
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("블로그", Path(".")))

    def raise_locked(collection, path):
        raise KeylensLockedError("잠김")

    monkeypatch.setattr(keylens_env, "fetch_env", raise_locked)

    with pytest.raises(KeylensLockedError):
        keylens_env.load_env()


def test_load_env_raises_when_collection_is_empty(monkeypatch):
    """빈 결과를 조용히 성공 처리하면 한참 뒤 엉뚱한 자리에서 KeyError로 터진다."""
    monkeypatch.setattr(keylens_env, "find_config", lambda: ("없는컬렉션", Path(".")))
    monkeypatch.setattr(keylens_env, "fetch_env", lambda c, p: {})

    with pytest.raises(KeylensEmptyCollectionError) as exc:
        keylens_env.load_env()

    assert "없는컬렉션" in str(exc.value)
    assert "collections" in str(exc.value)  # 다음에 뭘 하면 되는지 알려준다


def test_load_env_overrides_existing_env_by_default(monkeypatch):
    monkeypatch.setattr(keylens_env, "fetch_env", lambda c, p: {"K": "금고값"})
    monkeypatch.setenv("K", "원래값")

    keylens_env.load_env("c")

    assert os.environ["K"] == "금고값"


def test_load_env_respects_override_false(monkeypatch):
    """python-dotenv 처럼 기존 환경변수를 남겨 두는 선택지도 있어야 한다."""
    monkeypatch.setattr(keylens_env, "fetch_env", lambda c, p: {"K": "금고값", "NEW": "새값"})
    monkeypatch.setenv("K", "원래값")
    monkeypatch.delenv("NEW", raising=False)

    injected = keylens_env.load_env("c", override=False)

    assert os.environ["K"] == "원래값"  # 건드리지 않음
    assert os.environ["NEW"] == "새값"  # 없던 건 주입
    assert injected == {"NEW": "새값"}
