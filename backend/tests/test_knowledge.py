# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""지식베이스 로더 테스트."""
from app.knowledge import load_knowledge_base


def test_loads_all_services():
    kb = load_knowledge_base()
    assert {s.service for s in kb.services} == {"notion", "kakao", "gcp", "openai", "ollama"}


def test_credential_counts():
    kb = load_knowledge_base()
    # notion 4 + kakao 4 + gcp 1 + openai 2 + ollama 1 = 12
    assert kb.credential_count == 12


def test_official_env_names_unique():
    kb = load_knowledge_base()
    envs = [c.official_env_name for s in kb.services for c in s.credentials]
    assert len(envs) == len(set(envs))


def test_find():
    kb = load_knowledge_base()
    c = kb.find("notion", "database_id")
    assert c is not None and c.official_env_name == "NOTION_DATABASE_ID"
    assert kb.find("notion", "does_not_exist") is None


def test_value_matchers_only_prefix_clear_kinds():
    kb = load_knowledge_base()
    envs = {vm.credential.official_env_name for vm in kb.value_matchers}
    # 접두어가 명확한 종류만 value_regex 를 가진다
    assert {"NOTION_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENAI_ORG_ID", "OLLAMA_API_KEY"} <= envs
    # UUID·32hex 형식을 공유하는 종류는 value_regex 없음 (Stage2 대상)
    assert "NOTION_DATABASE_ID" not in envs
    assert "NOTION_PAGE_ID" not in envs
    assert "KAKAO_REST_API_KEY" not in envs
