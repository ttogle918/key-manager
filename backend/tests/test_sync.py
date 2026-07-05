# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""SYNC-0 암호화 금고 내보내기/가져오기 테스트.

핵심 보장: (1) 다른 기기에서 같은 마스터 비밀번호로 전체 복원,
(2) 틀린 비밀번호는 거부 + 기존 금고 무손상, (3) 번들에 평문 없음,
(4) 손상/구버전 파일은 명확한 에러(크래시 금지). 모든 키 값은 더미.
"""
from __future__ import annotations

import json

import pytest

from app import crypto, main
from app.models import VaultImportRequest
from app.vault_session import VaultLocked, VaultService

MASTER = "correct horse battery staple"
V1 = "sk-proj-DummyOpenAiValueOneTwoThree"
V2 = "ntn_DummyNotionValueFourFiveSixSevenEightNine012345"


def _svc(tmp_path, name: str) -> VaultService:
    return VaultService(str(tmp_path / name), auto_lock_seconds=60)


def _seed(svc: VaultService) -> None:
    svc.add_entry(service="openai", kind="api_key", official_name="OPENAI_API_KEY", value=V1)
    svc.add_entry(service="notion", kind="api_key", official_name="NOTION_API_KEY", value=V2)


# ── 라운드트립 ──
def test_export_import_replace_roundtrip(tmp_path):
    """내보낸 파일을 새 기기에서 가져오기 → 같은 마스터로 전체 항목 복원."""
    a = _svc(tmp_path, "a.db")
    a.init(MASTER)
    _seed(a)
    bundle = a.export_bundle()

    b = _svc(tmp_path, "b.db")  # 빈 새 기기
    res = b.import_bundle(bundle, MASTER, "replace")
    assert res == {"imported": 2, "skipped": 0, "mode": "replace"}

    byname = {m["official_name"]: m["id"] for m in b.list_entries()}
    assert b.get_value(byname["OPENAI_API_KEY"]) == V1
    assert b.get_value(byname["NOTION_API_KEY"]) == V2


def test_import_wrong_password_rejected_and_nondestructive(tmp_path):
    """틀린 마스터 비밀번호 → 복호화 거부, 기존 금고 무손상."""
    a = _svc(tmp_path, "a.db")
    a.init(MASTER)
    _seed(a)
    bundle = a.export_bundle()

    b = _svc(tmp_path, "b.db")
    b.init("a different master password")
    b.add_entry(service=None, kind=None, official_name="EXISTING_KEY", value="keep-me")

    with pytest.raises(crypto.DecryptError):
        b.import_bundle(bundle, "wrong password", "merge")

    metas = b.list_entries()
    assert len(metas) == 1 and metas[0]["official_name"] == "EXISTING_KEY"
    assert b.get_value(metas[0]["id"]) == "keep-me"


def test_bundle_has_no_plaintext(tmp_path):
    """내보낸 번들을 직접 열어도 평문 값이 없다(전부 암호문)."""
    a = _svc(tmp_path, "a.db")
    a.init(MASTER)
    _seed(a)
    blob = json.dumps(a.export_bundle())
    assert V1 not in blob and V2 not in blob
    assert MASTER not in blob


# ── 손상/버전 방어 ──
def test_import_not_keylens_file(tmp_path):
    b = _svc(tmp_path, "b.db")
    with pytest.raises(ValueError):
        b.import_bundle({"format": "something-else", "version": 1}, MASTER, "replace")


def test_import_unsupported_version(tmp_path):
    a = _svc(tmp_path, "a.db")
    a.init(MASTER)
    _seed(a)
    bundle = a.export_bundle()
    bundle["version"] = 999
    b = _svc(tmp_path, "b.db")
    with pytest.raises(ValueError):
        b.import_bundle(bundle, MASTER, "replace")


def test_import_corrupted_verifier(tmp_path):
    a = _svc(tmp_path, "a.db")
    a.init(MASTER)
    _seed(a)
    bundle = a.export_bundle()
    bundle["verifier"]["ct"] = "@@@not-valid-base64@@@"
    b = _svc(tmp_path, "b.db")
    with pytest.raises(ValueError):
        b.import_bundle(bundle, MASTER, "replace")


# ── 병합 ──
def test_merge_skips_duplicate_official_name(tmp_path):
    """병합: 중복 official_name 은 건너뛰고 기존 값 무손상, 새 항목만 추가."""
    a = _svc(tmp_path, "a.db")
    a.init(MASTER)
    _seed(a)  # OPENAI + NOTION
    bundle = a.export_bundle()

    b = _svc(tmp_path, "b.db")
    b.init(MASTER)
    b.add_entry(service=None, kind=None, official_name="OPENAI_API_KEY", value="pre-existing-openai")  # 중복

    res = b.import_bundle(bundle, MASTER, "merge")
    assert res["imported"] == 1 and res["skipped"] == 1

    byname = {m["official_name"]: m["id"] for m in b.list_entries()}
    assert b.get_value(byname["OPENAI_API_KEY"]) == "pre-existing-openai"  # 기존 무손상
    assert b.get_value(byname["NOTION_API_KEY"]) == V2  # 새로 병합됨


def test_merge_requires_unlocked_existing_vault(tmp_path):
    a = _svc(tmp_path, "a.db")
    a.init(MASTER)
    _seed(a)
    bundle = a.export_bundle()

    b = _svc(tmp_path, "b.db")
    b.init(MASTER)
    b.lock()
    with pytest.raises(VaultLocked):
        b.import_bundle(bundle, MASTER, "merge")


# ── 엔드포인트 상태코드 매핑 ──
@pytest.fixture
def vault(tmp_path, monkeypatch):
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    monkeypatch.setattr(main, "VAULT", svc)
    return svc


def test_export_when_locked_401(vault):
    from fastapi import HTTPException

    vault.init(MASTER)
    vault.lock()
    with pytest.raises(HTTPException) as e:
        main.vault_export()
    assert e.value.status_code == 401


def test_import_wrong_password_401(vault):
    from fastapi import HTTPException

    a_path = vault.db_path  # 재사용 안 함 — 별도 소스 번들 생성
    vault.init(MASTER)
    vault.add_entry(service=None, kind=None, official_name="OPENAI_API_KEY", value=V1)
    bundle = main.vault_export()
    with pytest.raises(HTTPException) as e:
        main.vault_import(VaultImportRequest(bundle=bundle, password="nope", mode="replace"))
    assert e.value.status_code == 401
    assert a_path  # db_path 접근 가능(경로 노출 sanity)


def test_import_corrupted_422(vault):
    from fastapi import HTTPException

    vault.init(MASTER)
    with pytest.raises(HTTPException) as e:
        main.vault_import(
            VaultImportRequest(bundle={"format": "nope"}, password=MASTER, mode="replace")
        )
    assert e.value.status_code == 422


def test_import_replace_via_endpoint(vault):
    """엔드포인트로 replace 가져오기 → 항목 복원 + 인증 유지."""
    vault.init(MASTER)
    vault.add_entry(service=None, kind=None, official_name="OPENAI_API_KEY", value=V1)
    bundle = main.vault_export()
    # 다른 항목만 남기려 교체: 새 번들 대신 동일 번들 재적용해도 결과 동일해야 함
    res = main.vault_import(
        VaultImportRequest(bundle=bundle, password=MASTER, mode="replace")
    )
    assert res.imported == 1 and res.mode == "replace"
    assert main.vault_status().unlocked is True  # 교체 후에도 인증 유지