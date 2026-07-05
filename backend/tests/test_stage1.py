# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Stage1 값 기반 분류 테스트.

⚠️ 모든 키는 명백한 더미 값 (CLAUDE.md 시크릿 위생).
"""
import pytest

from app.classify.stage1 import classify_text, extract_candidates
from app.knowledge import load_knowledge_base

# 명백히 가짜인 더미 키들 (형식만 유효, 실제 발급 키 아님)
OPENAI_KEY = "sk-proj-" + "a" * 20
OPENAI_LEGACY = "sk-" + "b" * 24
OPENAI_ORG = "org-" + "C" * 24
GOOGLE_KEY = "AIza" + "x" * 35
NOTION_SECRET = "secret_" + "A" * 43
NOTION_NTN = "ntn_" + "B" * 46
KAKAO_HEX = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"  # 32 hex
NOTION_UUID = "3f9a1c2e-7b4d-4e8a-9c1f-2d5e8a7b4c3f"


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


@pytest.mark.parametrize(
    "value,env,service",
    [
        (OPENAI_KEY, "OPENAI_API_KEY", "openai"),
        (OPENAI_LEGACY, "OPENAI_API_KEY", "openai"),
        (OPENAI_ORG, "OPENAI_ORG_ID", "openai"),
        (GOOGLE_KEY, "GOOGLE_API_KEY", "gcp"),
        (NOTION_SECRET, "NOTION_API_KEY", "notion"),
        (NOTION_NTN, "NOTION_API_KEY", "notion"),
    ],
)
def test_value_based_high_confidence(kb, value, env, service):
    items = classify_text(value, kb)
    assert len(items) == 1
    it = items[0]
    assert it.confidence == "high"
    assert it.official_env_name == env
    assert it.service == service
    assert "•" in it.masked  # 값이 마스킹됨
    assert value not in it.masked  # 원문 그대로 노출 안 됨


@pytest.mark.parametrize("value,fmt", [(KAKAO_HEX, "32자리 hex"), (NOTION_UUID, "UUID")])
def test_ambiguous_values_are_unknown(kb, value, fmt):
    """값만으로 애매한 것은 절대 단정하지 않고 unknown (SPEC 4.2 AC)."""
    items = classify_text(f"KEY={value}", kb)
    assert len(items) == 1
    it = items[0]
    assert it.confidence == "unknown"
    assert it.official_env_name is None
    assert it.format == fmt


def test_plain_words_are_ignored(kb):
    assert classify_text("hello world this is just prose", kb) == []


def test_assignment_captures_name(kb):
    items = classify_text(f"export OPENAI_API_KEY={OPENAI_KEY}", kb)
    assert len(items) == 1
    assert items[0].meta.get("assigned_name") == "OPENAI_API_KEY"


def test_env_block_multiple_keys(kb):
    block = "\n".join(
        [
            f"OPENAI_API_KEY={OPENAI_KEY}",
            f"GOOGLE_API_KEY={GOOGLE_KEY}",
            "# 주석은 무시",
            f"NOTION_TOKEN={NOTION_SECRET}",
        ]
    )
    items = classify_text(block, kb)
    envs = {it.official_env_name for it in items if it.confidence == "high"}
    assert {"OPENAI_API_KEY", "GOOGLE_API_KEY", "NOTION_API_KEY"} <= envs


def test_dedupes_same_value(kb):
    items = classify_text(f"{OPENAI_KEY} {OPENAI_KEY}", kb)
    assert len(items) == 1


# ── 값 절단 감지 (SECURITY_REVIEW 5-3) ──
def _trunc(text: str) -> dict[str, bool]:
    """extract_candidates 결과를 {값: 절단여부} 로."""
    return {v: t for v, origin, name, t in extract_candidates(text) if origin == "assignment"}


def test_truncation_unquoted_hash():
    """KEY=abc#def → 값이 # 에서 잘림 → truncated."""
    assert _trunc("KEY=abcdefghijkl#more")["abcdefghijkl"] is True


def test_truncation_embedded_quote():
    """따옴표 없이 값 안에 따옴표 → 잘림."""
    assert _trunc("KEY=abcdefghijkl\"more")["abcdefghijkl"] is True


def test_quoted_value_natural_close_not_truncated():
    """정상적으로 따옴표로 감싼 값은 절단 아님."""
    assert _trunc('KEY="abcdefghijkl"')["abcdefghijkl"] is False


def test_plain_value_not_truncated():
    assert _trunc(f"OPENAI_API_KEY={OPENAI_KEY}")[OPENAI_KEY] is False


def test_truncated_flag_reaches_meta(kb):
    """분류 결과 meta 에 truncated 가 전달된다(프론트 경고용)."""
    items = classify_text("MY_TOKEN=abcdefghijkl#trailing", kb)
    hit = next(it for it in items if it.value == "abcdefghijkl")
    assert hit.meta.get("truncated") is True
