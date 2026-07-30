# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""VAULT-1 암호화 코어 — Argon2id 키 유도 + AES-256-GCM (SPEC 6장).

원칙: **마스터 비밀번호도, 유도된 키도 절대 디스크에 저장하지 않는다.**
디스크에는 KDF 솔트·파라미터와 암호문(nonce+태그 포함)만 남는다. 키는 이 프로세스 메모리에만 존재한다.

- 키 유도: Argon2id(메모리-하드) 로 마스터 비밀번호 → 32바이트 대칭키. 솔트는 항목이 아니라 금고 단위.
- 암호화: 항목별 AES-256-GCM. 매 암호화마다 새 nonce(12B). GCM 태그로 무결성·인증 → 변조/오답 비밀번호 거부.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, replace

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

KEY_LEN = 32  # AES-256
SALT_LEN = 16
NONCE_LEN = 12

# Argon2id 기본 강도 — 대화형 로컬 앱에 맞춘 값(메모리 64MiB). 금고 생성 시점에 확정·저장한다.
DEFAULT_TIME_COST = 3
DEFAULT_MEMORY_KIB = 64 * 1024  # 64 MiB
DEFAULT_LANES = 4


class DecryptError(Exception):
    """복호화 실패 — 틀린 비밀번호이거나 데이터 변조(GCM 태그 불일치)."""


class WeakPasswordError(ValueError):
    """마스터 비밀번호가 비밀번호 작성규칙을 충족하지 못함."""


def check_password_strength(password: str) -> None:
    """개인정보보호위원회 '개인정보의 안전성 확보조치 기준' 비밀번호 작성규칙을 강제한다.

    영문·숫자·특수문자 중 3종류 이상을 조합하면 8자 이상, 2종류만 조합하면 10자 이상이어야
    한다(1종류만 쓰면 길이와 무관하게 거부). 기존 min_length=8 pydantic 제약은 절대 하한일
    뿐이고, 조합이 2종류면 이 함수가 10자 이상을 추가로 요구한다.
    """
    kinds = sum(
        [
            any(c.isalpha() for c in password),
            any(c.isdigit() for c in password),
            any(not c.isalnum() for c in password),
        ]
    )
    if kinds < 2:
        raise WeakPasswordError("비밀번호는 영문·숫자·특수문자 중 2종류 이상을 섞어야 해요.")
    min_len = 8 if kinds >= 3 else 10
    if len(password) < min_len:
        raise WeakPasswordError(
            f"영문·숫자·특수문자를 {'모두' if kinds >= 3 else '2종류'} 섞었다면 {min_len}자 이상이어야 해요."
        )


@dataclass(frozen=True)
class KdfParams:
    """금고에 저장되는 키 유도 파라미터(비밀 아님). 같은 비밀번호+같은 파라미터 → 같은 키."""

    salt: bytes
    time_cost: int = DEFAULT_TIME_COST
    memory_cost: int = DEFAULT_MEMORY_KIB
    lanes: int = DEFAULT_LANES


def new_params() -> KdfParams:
    """새 금고용 KDF 파라미터(무작위 솔트 + 기본 강도)."""
    return KdfParams(salt=os.urandom(SALT_LEN))


def derive_key(password: str, params: KdfParams) -> bytes:
    """마스터 비밀번호 → 32바이트 키. 반환 키는 호출자가 메모리에서만 다뤄야 한다."""
    kdf = Argon2id(
        salt=params.salt,
        length=KEY_LEN,
        iterations=params.time_cost,
        lanes=params.lanes,
        memory_cost=params.memory_cost,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt(key: bytes, plaintext: str, aad: bytes | None = None) -> tuple[bytes, bytes]:
    """평문 → (nonce, 암호문+태그). aad(부가 인증 데이터)는 암호화되진 않지만 무결성에 묶인다."""
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), aad)
    return nonce, ct


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes | None = None) -> str:
    """(nonce, 암호문+태그) → 평문. 키가 틀리거나 변조되면 DecryptError."""
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad).decode("utf-8")
    except InvalidTag as e:
        raise DecryptError("복호화 실패 — 비밀번호가 틀렸거나 데이터가 변조됨") from e


def with_new_salt(params: KdfParams) -> KdfParams:
    """비밀번호 변경 시 새 솔트로 파라미터 재발급(같은 강도 유지)."""
    return replace(params, salt=os.urandom(SALT_LEN))
