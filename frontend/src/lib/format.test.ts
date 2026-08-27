// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * format 유틸 테스트 — TRUST-2의 JWT 만료일 자동 추출(jwtExp)에 집중.
 * 모든 토큰은 더미이며 서명 검증은 하지 않는다(만료일 표기만 목적).
 */
import { describe, expect, it } from 'vitest'
import { jwtExp, passwordPolicyError, projectKey } from './format'
import type { VaultItem } from '@/types'

/** base64url payload로 더미 JWT를 만든다(header/signature는 형식만 맞춘 더미). */
function makeJwt(payload: Record<string, unknown>): string {
  const b64 = btoa(JSON.stringify(payload))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
  return `eyJhbGciOiJIUzI1NiJ9.${b64}.ZHVtbXlzaWc`
}

describe('jwtExp', () => {
  it('exp 클레임을 YYYY-MM-DD로 추출한다', () => {
    // 2026-07-04 00:00:00 UTC 근처 — 로컬 타임존에 따라 날짜가 하루 흔들릴 수 있어
    // 정오(UTC)로 잡아 KST(+9)에서도 같은 날짜가 되게 한다.
    const exp = Math.floor(Date.UTC(2026, 6, 4, 12, 0, 0) / 1000)
    expect(jwtExp(makeJwt({ exp }))).toBe('2026-07-04')
  })

  it('JWT 형식(3파트)이 아니면 null', () => {
    expect(jwtExp('not-a-jwt')).toBeNull()
    expect(jwtExp('only.two')).toBeNull()
    expect(jwtExp('a.b.c.d')).toBeNull()
  })

  it('exp 클레임이 없으면 null(생짜 API 키류)', () => {
    expect(jwtExp(makeJwt({ sub: 'user-1' }))).toBeNull()
  })

  it('exp가 숫자가 아니면 null', () => {
    expect(jwtExp(makeJwt({ exp: '1893456000' }))).toBeNull()
  })

  it('payload가 유효한 base64/JSON이 아니면 null', () => {
    expect(jwtExp('aaa.@@@notbase64@@@.bbb')).toBeNull()
  })

  it('일반 API 키 값(점 2개짜리 Ollama형)도 오탐 없이 null', () => {
    // 32hex + '.' + base62 24 — 점이 1개라 3파트가 아니므로 null.
    expect(
      jwtExp('abcdef0123456789abcdef0123456789.DummyOllamaSuffix1234567'),
    ).toBeNull()
  })
})

describe('passwordPolicyError', () => {
  // 개인정보보호위원회 '개인정보의 안전성 확보조치 기준': 3종류 조합 8자 / 2종류 조합 10자.
  it('문자 종류가 1개뿐이면 길이와 무관하게 거부', () => {
    expect(passwordPolicyError('alllowercase')).not.toBeNull()
    expect(passwordPolicyError('12345678901234')).not.toBeNull()
  })

  it('2종류 조합은 10자 미만이면 거부, 10자 이상이면 통과', () => {
    expect(passwordPolicyError('abc12345')).not.toBeNull() // 8자 < 10
    expect(passwordPolicyError('abcdefgh12')).toBeNull() // 정확히 10자
  })

  it('3종류(영문+숫자+특수문자) 조합은 8자면 통과', () => {
    expect(passwordPolicyError('Abcd12!@')).toBeNull()
  })

  it('3종류 조합이어도 8자 미만이면 거부', () => {
    expect(passwordPolicyError('Ab1!')).not.toBeNull()
  })
})

function makeVaultItem(overrides: Partial<VaultItem> = {}): VaultItem {
  return {
    id: '1',
    service: 'OpenAI',
    type: 'API Key',
    varName: 'OPENAI_API_KEY',
    masked: 'sk-****',
    full: 'sk-dummy',
    addedAt: '2026-08-27',
    project: '',
    context: '',
    memo: '',
    sourceImage: null,
    expiresAt: null,
    history: [],
    meta: {},
    ...overrides,
  }
}

describe('projectKey', () => {
  it('project가 있으면 그대로 쓴다', () => {
    expect(projectKey(makeVaultItem({ project: '블로그' }))).toBe('블로그')
  })

  it('project가 빈 문자열이면 등록일(addedAt)로 대체한다', () => {
    expect(projectKey(makeVaultItem({ project: '', addedAt: '2026-08-27' }))).toBe('2026-08-27')
  })
})
