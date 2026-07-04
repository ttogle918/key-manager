# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""Stage2 맥락 기반 분류 테스트 (차별점). 모든 값은 더미."""
import pytest

from app.classify.pipeline import analyze
from app.classify.stage2 import classify_context
from app.knowledge import load_knowledge_base
from app.models import AnalyzeRequest

UUID_DASH = "3f9a1c2e-7b4d-4e8a-9c1f-2d5e8a7b4c3f"
HEX32 = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
DB_URL = "https://www.notion.so/team/3f9a1c2e7b4d4e8a9c1f2d5e8a7b4c3f?v=9c1f2d5e"
PAGE_URL = "https://www.notion.so/myws/Weekly-Notes-" + HEX32


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


def test_url_database_id(kb):
    """notion DB URL(?v= 앞 세그먼트) → database_id, 강한 신호 → high."""
    items = classify_context("", DB_URL, kb)
    assert len(items) == 1
    assert items[0].official_env_name == "NOTION_DATABASE_ID"
    assert items[0].confidence == "high"


def test_url_page_id_is_weaker(kb):
    """page URL 마지막 세그먼트는 위치 신호 → page_id, 약한 신호 → medium."""
    items = classify_context("", PAGE_URL, kb)
    assert len(items) == 1
    assert items[0].official_env_name == "NOTION_PAGE_ID"
    assert items[0].confidence == "medium"


def test_label_database_id(kb):
    """'Database ID' 라벨 옆 UUID → database_id."""
    items = classify_context(f"Database ID\n{UUID_DASH}", "", kb)
    assert len(items) == 1
    assert items[0].official_env_name == "NOTION_DATABASE_ID"
    assert items[0].confidence == "high"


def test_label_kakao_rest(kb):
    """카카오 32hex는 값이 같아 구분 불가 — 'REST API 키' 라벨로 종류 확정."""
    items = classify_context(f"REST API 키\n{HEX32}", "", kb)
    assert len(items) == 1
    assert items[0].official_env_name == "KAKAO_REST_API_KEY"


def test_signal_conflict_flags_not_asserts(kb):
    """라벨(data_source) vs URL 위치(page) 충돌 → 단정 없이 conflict + 선택지(SPEC 4.3 AC)."""
    text = f"Data sources\n{HEX32}"
    url = "https://www.notion.so/ws/Panel-" + HEX32
    items = classify_context(text, url, kb)
    assert len(items) == 1
    it = items[0]
    assert it.conflict is True
    assert it.confidence == "low"
    assert it.official_env_name is None
    envs = {o.official_env_name for o in it.options}
    assert envs == {"NOTION_DATA_SOURCE_ID", "NOTION_PAGE_ID"}


def test_pipeline_merges_stage1_and_stage2(kb):
    """Stage1(값 기반 sk-) + Stage2(라벨 UUID)가 한 응답에 병합된다."""
    text = f"OPENAI_API_KEY=sk-proj-{'a' * 20}\nDatabase ID\n{UUID_DASH}"
    resp = analyze(AnalyzeRequest(text=text), kb)
    by_env = {it.official_env_name: it for it in resp.items}
    assert "OPENAI_API_KEY" in by_env and by_env["OPENAI_API_KEY"].confidence == "high"
    assert "NOTION_DATABASE_ID" in by_env
    # Stage1이 UUID를 unknown으로 낸 뒤 Stage2가 대체 — 중복 없이 1건
    assert sum(1 for it in resp.items if it.value == UUID_DASH) == 1


def test_pipeline_url_only(kb):
    """URL만 입력해도 구조로 분류된다(텍스트 없음)."""
    resp = analyze(AnalyzeRequest(url=DB_URL), kb)
    assert resp.count == 1
    assert resp.items[0].official_env_name == "NOTION_DATABASE_ID"
