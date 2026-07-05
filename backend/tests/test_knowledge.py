# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""지식베이스 로더 테스트."""
import pytest

from app.knowledge import DEFAULT_KNOWLEDGE_DIR, load_knowledge_base


def test_loads_all_services():
    kb = load_knowledge_base()
    # 새 YAML 추가에 덜 취약하도록 최소 보장 집합으로 검증(초과는 허용).
    expected = {"notion", "kakao", "gcp", "openai", "ollama", "github", "aws", "slack", "stripe"}
    assert expected <= {s.service for s in kb.services}


def test_credential_counts():
    kb = load_knowledge_base()
    # notion 4 + kakao 4 + gcp 1 + openai 2 + ollama 1 + github 1 + aws 2 + slack 2 + stripe 2 = 19
    assert kb.credential_count == 19


def test_official_env_names_unique():
    kb = load_knowledge_base()
    envs = [c.official_env_name for s in kb.services for c in s.credentials]
    assert len(envs) == len(set(envs))


def test_find():
    kb = load_knowledge_base()
    c = kb.find("notion", "database_id")
    assert c is not None and c.official_env_name == "NOTION_DATABASE_ID"
    assert kb.find("notion", "does_not_exist") is None


def test_knowledge_dir_env_override(tmp_path, monkeypatch):
    """KEYLENS_KNOWLEDGE_DIR 로 지식베이스 위치를 재정의(패키징된 데스크톱 앱 대비)."""
    (tmp_path / "only.yaml").write_text(
        "service: only\n"
        "display_name: Only\n"
        "credentials:\n"
        "  - kind: api_key\n"
        "    label: API Key\n"
        "    official_env_name: ONLY_API_KEY\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KEYLENS_KNOWLEDGE_DIR", str(tmp_path))
    kb = load_knowledge_base()  # 인자 없음 → env 경로 사용
    assert {s.service for s in kb.services} == {"only"}
    # 명시 인자는 env 보다 우선한다
    kb2 = load_knowledge_base(DEFAULT_KNOWLEDGE_DIR)
    assert "notion" in {s.service for s in kb2.services}


def test_value_matchers_only_prefix_clear_kinds():
    kb = load_knowledge_base()
    envs = {vm.credential.official_env_name for vm in kb.value_matchers}
    # 접두어가 명확한 종류만 value_regex 를 가진다
    assert {"NOTION_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "OPENAI_ORG_ID", "OLLAMA_API_KEY"} <= envs
    # UUID·32hex 형식을 공유하는 종류는 value_regex 없음 (Stage2 대상)
    assert "NOTION_DATABASE_ID" not in envs
    assert "NOTION_PAGE_ID" not in envs
    assert "KAKAO_REST_API_KEY" not in envs


# ── 잘못된 YAML 방어 (기동 실패 진단성 — CORE-4 / OSS-1) ──
def test_missing_directory_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_knowledge_base(tmp_path / "does_not_exist")


def test_malformed_yaml_names_file(tmp_path):
    (tmp_path / "broken.yaml").write_text("service: x\n  bad: : indent", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.yaml"):
        load_knowledge_base(tmp_path)


def test_schema_violation_names_file(tmp_path):
    # credentials 누락 → 스키마 위반, 에러에 파일명 포함
    (tmp_path / "noservice.yaml").write_text("display_name: X\n", encoding="utf-8")
    with pytest.raises(ValueError, match="noservice.yaml"):
        load_knowledge_base(tmp_path)


def test_bad_regex_names_file_and_kind(tmp_path):
    (tmp_path / "badre.yaml").write_text(
        "service: s\ndisplay_name: S\ncredentials:\n"
        "  - kind: api_key\n    label: K\n    value_regex: '([unclosed'\n"
        "    official_env_name: S_KEY\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="badre.yaml"):
        load_knowledge_base(tmp_path)


def test_duplicate_env_name_across_files(tmp_path):
    for n in ("a.yaml", "b.yaml"):
        (tmp_path / n).write_text(
            f"service: {n[0]}\ndisplay_name: {n[0]}\ncredentials:\n"
            "  - kind: api_key\n    label: K\n    official_env_name: DUP_KEY\n",
            encoding="utf-8",
        )
    with pytest.raises(ValueError, match="중복 official_env_name"):
        load_knowledge_base(tmp_path)
