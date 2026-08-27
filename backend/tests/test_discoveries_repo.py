# SPDX-FileCopyrightText: 2026 ttogle918
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


def test_find_by_pattern_returns_none_on_malformed_yaml(tmp_path):
    """중단된 쓰기 등으로 파일이 깨진 YAML이어도 예외 대신 캐시 미스로 처리한다."""
    path = tmp_path / "local_discoveries.yaml"
    path.write_text("pattern: [unterminated", encoding="utf-8")
    assert find_by_pattern(path, "아무 패턴") is None


def test_find_by_pattern_skips_non_dict_entries(tmp_path):
    """리스트 최상위 모양은 맞지만 원소가 dict가 아닌 손상 파일도 죽지 않는다."""
    path = tmp_path / "local_discoveries.yaml"
    path.write_text("- oops\n- 42\n", encoding="utf-8")
    assert find_by_pattern(path, "아무 패턴") is None
