# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""local_discoveries.yaml 읽기/쓰기 — 항상 confirmed: false로 저장되는지, 정규화 매칭이 값은
무시하고 라벨 문구만 비교하는지가 핵심."""
import threading

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


def test_normalize_pattern_preserves_underscored_label_without_digits():
    """"Project_ID"처럼 _만 있고 숫자가 없는 라벨 문구는 더 이상 지워지지 않는다 — 예전 정규식은
    이걸 지워서 서로 다른 라벨("Project_ID" vs "Database_ID")이 동일한 <VALUE> 패턴으로 뭉개졌다."""
    assert normalize_pattern("Project_ID: abc123def456") == "Project_ID: <VALUE>"
    assert normalize_pattern("Database_ID: xyz789ghi012") == "Database_ID: <VALUE>"


def test_normalize_pattern_redacts_long_hex_only_token_without_digits():
    """숫자가 하나도 없어도 8자 이상 순수 16진수 문자열(예: 헥스 시크릿)은 값으로 취급해 지운다."""
    assert normalize_pattern("Secret: deadbeefcafebabe") == "Secret: <VALUE>"


def test_find_by_pattern_skips_entry_missing_required_key(tmp_path):
    """tier 키가 아예 없는 손상된 항목은 조회 시 건너뛴다(과거엔 KeyError로 파이프라인이 깨졌음)."""
    path = tmp_path / "local_discoveries.yaml"
    path.write_text("- pattern: 'API Key: <VALUE>'\n  label: 예시\n", encoding="utf-8")
    assert find_by_pattern(path, "API Key: <VALUE>") is None


def test_find_by_pattern_skips_entry_with_invalid_tier(tmp_path):
    """tier 값이 알려진 3종(known/ai_verified/ai_unverified) 밖이면 건너뛴다(과거엔 ExplainBox
    생성 시 Pydantic ValidationError로 파이프라인이 깨졌음)."""
    path = tmp_path / "local_discoveries.yaml"
    path.write_text(
        "- pattern: 'X'\n  label: 예시\n  tier: bogus\n  docs_url: null\n", encoding="utf-8"
    )
    assert find_by_pattern(path, "X") is None


def test_append_discovery_survives_concurrent_calls_without_losing_entries(tmp_path):
    """"저장" 버튼을 여러 개 거의 동시에 눌러도(스레드풀에서 병렬 실행) 항목이 유실되지 않는다 —
    write_lock이 read-modify-write 구간을 직렬화해야 한다."""
    path = tmp_path / "local_discoveries.yaml"
    threads = [
        threading.Thread(
            target=append_discovery,
            kwargs=dict(path=path, pattern=f"P{i}", label=f"라벨{i}", tier="ai_unverified", docs_url=None),
        )
        for i in range(20)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i in range(20):
        found = find_by_pattern(path, f"P{i}")
        assert found is not None, f"P{i} 항목이 동시 쓰기로 유실됨"
        assert found["label"] == f"라벨{i}"


def test_append_discovery_leaves_no_tmp_file_behind(tmp_path):
    """원자적 쓰기(임시 파일 + os.replace)가 정상 경로에서 .tmp 파일을 남기지 않는지 확인."""
    path = tmp_path / "local_discoveries.yaml"
    append_discovery(path, pattern="A", label="B", tier="ai_unverified", docs_url=None)
    assert not (tmp_path / "local_discoveries.yaml.tmp").exists()
    assert path.exists()


def test_normalize_pattern_redacts_dashed_prefix_token_without_digits(tmp_path):
    """"sk-proj-AbCdEfGhIjKl"처럼 숫자도 순수 16진수도 아니지만 -/_ 를 포함한 12자 이상 접두어형
    토큰도 값으로 취급한다 — API 키 접두어(sk-, ghp_ 등)는 숫자 없이도 흔하다."""
    assert normalize_pattern("Key: sk-proj-AbCdEfGhIjKl") == "Key: <VALUE>"


def test_find_by_pattern_skips_entry_with_non_string_docs_url(tmp_path):
    """docs_url이 문자열도 null도 아니면(예: 숫자) 건너뛴다 — 그대로 뒀으면 ExplainBox 생성 시
    Pydantic ValidationError로 파이프라인이 깨졌을 것."""
    path = tmp_path / "local_discoveries.yaml"
    path.write_text(
        "- pattern: 'X'\n  label: 예시\n  tier: known\n  docs_url: 42\n", encoding="utf-8"
    )
    assert find_by_pattern(path, "X") is None
