# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""신규 지식베이스 4종(GitHub·AWS·Slack·Stripe) 값 기반 분류 테스트.

핵심: 코드 수정 0, YAML 추가만으로 새 서비스가 분류 대상에 포함되는지 검증.
⚠️ 모든 키는 명백한 더미(형식만 유효, 실제 발급 키 아님).
"""
import pytest

from app.classify.stage1 import classify_text
from app.knowledge import load_knowledge_base

# 더미 키(형식만 유효) — CLAUDE.md 시크릿 위생
GITHUB_CLASSIC = "ghp_" + "A" * 36
GITHUB_FINE = "github_pat_" + "B" * 50
AWS_AKIA = "AKIAIOSFODNN7EXAMPLE"  # AWS 공식 문서 예시 형식(AKIA + 16)
AWS_ASIA = "ASIA" + "1234567890ABCDEF"
SLACK_BOT = "xoxb-123456789012-1234567890123-" + "a" * 24
SLACK_USER = "xoxp-123456789012-1234567890123-" + "b" * 24
STRIPE_SK = "sk_test_" + "A" * 24
STRIPE_RK = "rk_live_" + "B" * 30
STRIPE_PK = "pk_test_" + "C" * 24


@pytest.fixture(scope="module")
def kb():
    return load_knowledge_base()


def test_kb_loads_with_new_services(kb):
    ids = {s.service for s in kb.services}
    assert {"github", "aws", "slack", "stripe"} <= ids


@pytest.mark.parametrize(
    "value,env,service",
    [
        (GITHUB_CLASSIC, "GITHUB_TOKEN", "github"),
        (GITHUB_FINE, "GITHUB_TOKEN", "github"),
        (AWS_AKIA, "AWS_ACCESS_KEY_ID", "aws"),
        (AWS_ASIA, "AWS_ACCESS_KEY_ID", "aws"),
        (SLACK_BOT, "SLACK_BOT_TOKEN", "slack"),
        (SLACK_USER, "SLACK_USER_TOKEN", "slack"),
        (STRIPE_SK, "STRIPE_SECRET_KEY", "stripe"),
        (STRIPE_RK, "STRIPE_SECRET_KEY", "stripe"),
        (STRIPE_PK, "STRIPE_PUBLISHABLE_KEY", "stripe"),
    ],
)
def test_value_based_classification(kb, value, env, service):
    items = classify_text(value, kb)
    assert len(items) == 1, f"{value!r} → {items}"
    it = items[0]
    assert it.confidence == "high"
    assert it.official_env_name == env
    assert it.service == service


def test_stripe_underscore_not_confused_with_openai(kb):
    """OpenAI 는 'sk-'(하이픈), Stripe 는 'sk_'(언더스코어) — 서로 오분류 금지."""
    openai = classify_text("sk-proj-" + "a" * 20, kb)
    assert openai and openai[0].service == "openai"
    stripe = classify_text("sk_live_" + "Z" * 24, kb)
    assert stripe and stripe[0].service == "stripe"


def test_aws_secret_key_not_value_classified(kb):
    """접두어 없는 AWS 시크릿(40 base64)은 값만으론 단정하지 않는다(오탐 금지)."""
    secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # 40자, AWS 문서 예시 형식
    items = classify_text(secret, kb)
    # 값 기반으론 AWS_SECRET_ACCESS_KEY 로 단정되지 않아야 한다(high 매핑 없음).
    assert not any(
        it.official_env_name == "AWS_SECRET_ACCESS_KEY" and it.confidence == "high"
        for it in items
    )


GCP_OAUTH_ID = "123456789012-abcdefghijklmnopqrstuvwxyz012345.apps.googleusercontent.com"
GCP_OAUTH_SECRET = "GOCSPX-" + "AbCdEfGhIjKlMnOpQrStUvWx"


@pytest.mark.parametrize(
    "value,env",
    [
        (GCP_OAUTH_ID, "GOOGLE_CLIENT_ID"),
        (GCP_OAUTH_SECRET, "GOOGLE_CLIENT_SECRET"),
    ],
)
def test_gcp_oauth_value_based(kb, value, env):
    """GCP OAuth 클라이언트 ID/시크릿은 접두어·도메인이 특징적이라 값만으로 식별."""
    items = classify_text(value, kb)
    assert len(items) == 1
    assert items[0].service == "gcp"
    assert items[0].official_env_name == env
    assert items[0].confidence == "high"


def test_gcp_service_account_json_not_value_classified(kb):
    """서비스 계정 키(JSON)는 파일이라 값만으론 단정하지 않는다(라벨 맥락 전용)."""
    # 서비스 계정 JSON 조각(더미) — 값 기반으로 GOOGLE_APPLICATION_CREDENTIALS 로 단정 금지.
    blob = '{"type":"service_account","project_id":"demo","private_key_id":"abc123"}'
    items = classify_text(blob, kb)
    assert not any(
        it.official_env_name == "GOOGLE_APPLICATION_CREDENTIALS" and it.confidence == "high"
        for it in items
    )


def test_gcp_api_key_still_works(kb):
    """기존 GCP API 키(AIza) 분류가 종류 추가 후에도 유지되는지 회귀 확인."""
    items = classify_text("AIza" + "x" * 35, kb)
    assert len(items) == 1 and items[0].official_env_name == "GOOGLE_API_KEY"


def test_random_string_no_false_positive(kb):
    """무작위 문자열은 어떤 신규 서비스로도 high 분류되지 않는다."""
    items = classify_text("just-some-random-text-not-a-key", kb)
    new_envs = {
        "GITHUB_TOKEN", "AWS_ACCESS_KEY_ID", "SLACK_BOT_TOKEN",
        "SLACK_USER_TOKEN", "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY",
    }
    assert not any(
        it.official_env_name in new_envs and it.confidence == "high" for it in items
    )
