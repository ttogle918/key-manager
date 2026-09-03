# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""PostgreSQL 연결 문자열 값 기반 분류 테스트.

여기서 검증하는 건 **사용자의 .env 에 들어 있는 연결 문자열**을 알아보는지다.
KeyLens 자체 저장소는 SQLite 이고 이 파일과 무관하다.

핵심 경계: `postgres://user:pw@host/db` 는 URL 안에 비밀번호가 평문으로 들어 있어
자격증명이지만, `postgres://localhost/db` 는 비밀번호가 없어 그냥 설정이다.
후자를 시크릿으로 잡으면 사용자가 "이게 왜 키야?" 하게 되고, 전자를 놓치면
비밀번호가 평문으로 방치된다. 그 경계가 이 테스트의 존재 이유다.

⚠️ 모든 값은 명백한 더미(형식만 유효, 실제 접속 정보 아님).
"""
import pytest

from app.classify.stage1 import classify_text
from app.knowledge import load_knowledge_base

# 더미 연결 문자열 — 형식만 유효, 실제로 접속되지 않는다
PG_BASIC = "postgres://appuser:dummypass@localhost:5432/appdb"
PG_FULL = "postgresql://admin:dummysecret@db.example.com:5432/mydb?sslmode=require"
PG_SHORT = "postgres://u:p@host/db"
PG_MANAGED = "postgres://reader:dummy123@aws-0-ap-northeast-2.example.com:6543/postgres"


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


def test_kb_loads_with_postgresql(kb):
    assert "postgresql" in {s.service for s in kb.services}


@pytest.mark.parametrize("value", [PG_BASIC, PG_FULL, PG_SHORT, PG_MANAGED])
def test_connection_url_is_classified(kb, value):
    """비밀번호가 들어간 연결 문자열은 PostgreSQL 자격증명으로 분류된다."""
    items = classify_text(value, kb)
    assert len(items) == 1
    assert items[0].service == "postgresql"
    assert items[0].official_env_name == "DATABASE_URL"
    assert items[0].kind == "connection_url"


@pytest.mark.parametrize(
    "value",
    [
        "postgres://localhost/mydb",       # 비밀번호 없음 = 설정이지 시크릿 아님
        "postgresql://user@host/db",       # 사용자만 있고 비밀번호 없음
    ],
)
def test_url_without_password_is_not_a_credential(kb, value):
    """자격증명이 없는 연결 URL 은 잡지 않는다 - 시크릿이 아니라 설정이다.

    이걸 잡아버리면 DB_HOST 류 설정까지 시크릿으로 승격돼 노출 등급 표시가 무의미해진다.
    """
    items = classify_text(value, kb)
    assert not any(it.official_env_name == "DATABASE_URL" for it in items)


@pytest.mark.parametrize(
    "value",
    [
        "mysql://user:dummypass@host/db",
        "mongodb://user:dummypass@host/db",
        "redis://user:dummypass@host:6379/0",
        "https://user:dummypass@example.com/path",
    ],
)
def test_other_schemes_not_misread_as_postgres(kb, value):
    """다른 DB·프로토콜의 연결 문자열을 PostgreSQL 로 둔갑시키지 않는다."""
    items = classify_text(value, kb)
    assert not any(it.service == "postgresql" for it in items)


def test_random_string_no_false_positive(kb):
    items = classify_text("just-some-random-text-not-a-connection-string", kb)
    assert not any(
        it.official_env_name == "DATABASE_URL" and it.confidence == "high"
        for it in items
    )


def test_database_url_env_name_is_unique(kb):
    """official_env_name 은 지식베이스 전체에서 유일해야 한다(로더도 강제하지만 명시).

    DATABASE_URL 이 다른 서비스와 겹치면 findServiceByVarName 이 엉뚱한 서비스를 돌려주고,
    가져오기 표의 "제안" 도 틀린 이름을 권하게 된다.
    """
    names = [c.official_env_name for s in kb.services for c in s.credentials]
    assert names.count("DATABASE_URL") == 1
