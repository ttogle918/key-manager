// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { SERVICE_ORDER } from '@/data/services'
import type { VaultItem } from '@/types'

const BULLET = '\u2022'

/**
 * 보관함 그룹핑용 컬렉션 키. 컬렉션(project 필드) 미지정 항목은 등록일로 묶는다 — 백엔드가 새 저장 시
 * 실제 project 값을 등록일로 채워주지만(main.vault_add), 마이그레이션하지 않은 기존 항목은
 * 여전히 project가 빈 문자열일 수 있어 화면에서도 동일 규칙으로 방어한다.
 */
export function projectKey(it: VaultItem): string {
  return it.project || it.addedAt
}

/** 오늘 날짜(YYYY-MM-DD, 로컬). */
export function today(): string {
  const d = new Date()
  return (
    d.getFullYear() +
    '-' +
    String(d.getMonth() + 1).padStart(2, '0') +
    '-' +
    String(d.getDate()).padStart(2, '0')
  )
}

/** ISO 날짜를 한국어 표기로. full=true면 "2026년 5월 28일", 아니면 "5월 28일". */
export function fmtDate(iso: string | null, full = false): string {
  if (!iso) return ''
  const p = iso.split('-').map(Number)
  return full ? `${p[0]}년 ${p[1]}월 ${p[2]}일` : `${p[1]}월 ${p[2]}일`
}

export interface ExpiryInfo {
  days: number
  label: string
  expired: boolean
  urgent: boolean
}

/** 만료일까지 남은 일수 정보. */
export function expiryInfo(iso: string | null): ExpiryInfo | null {
  if (!iso) return null
  const days = Math.round(
    (new Date(iso + 'T00:00:00').getTime() -
      new Date(new Date().toDateString()).getTime()) /
      86400000,
  )
  return {
    days,
    label: days < 0 ? '만료됨' : 'D-' + days,
    expired: days < 0,
    urgent: days <= 3,
  }
}

/**
 * JWT(`header.payload.signature`)의 `exp` 클레임을 만료일(YYYY-MM-DD)로 추출한다.
 * JWT가 아니거나 exp가 없으면 null — 생짜 API 키엔 만료 정보가 없으므로 사용자 입력으로 대체(TRUST-2).
 */
export function jwtExp(value: string): string | null {
  const parts = value.trim().split('.')
  if (parts.length !== 3) return null
  try {
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const pad = b64.length % 4 ? '='.repeat(4 - (b64.length % 4)) : ''
    const payload = JSON.parse(atob(b64 + pad)) as { exp?: unknown }
    if (typeof payload.exp !== 'number' || !isFinite(payload.exp)) return null
    const d = new Date(payload.exp * 1000)
    if (isNaN(d.getTime())) return null
    return (
      d.getFullYear() +
      '-' +
      String(d.getMonth() + 1).padStart(2, '0') +
      '-' +
      String(d.getDate()).padStart(2, '0')
    )
  } catch {
    return null
  }
}

/**
 * 개인정보보호위원회 '개인정보의 안전성 확보조치 기준' 비밀번호 작성규칙.
 * 영문·숫자·특수문자 중 3종류 이상 조합 시 8자 이상, 2종류만 조합 시 10자 이상이어야 한다
 * (1종류만 쓰면 길이와 무관하게 거부). 백엔드(`crypto.check_password_strength`)와 동일 규칙 —
 * 여기서는 제출 전에 미리 막아 왕복을 줄이는 용도이고, 최종 판단은 백엔드가 한다.
 */
export function passwordPolicyError(pw: string): string | null {
  const kinds =
    Number(/[A-Za-z]/.test(pw)) + Number(/\d/.test(pw)) + Number(/[^A-Za-z0-9]/.test(pw))
  if (kinds < 2) return '비밀번호는 영문·숫자·특수문자 중 2종류 이상을 섞어야 해요.'
  const minLen = kinds >= 3 ? 8 : 10
  if (pw.length < minLen) {
    return `영문·숫자·특수문자를 ${kinds >= 3 ? '모두' : '2종류'} 섞었다면 ${minLen}자 이상이어야 해요.`
  }
  return null
}

/** 마스터 비밀번호 강도 (0=빈값 ~ 4=강함). */
export function strengthLevel(pw: string): number {
  if (!pw.length) return 0
  let sc = 0
  if (pw.length >= 8) sc++
  if (pw.length >= 12) sc++
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) sc++
  if (/\d/.test(pw)) sc++
  if (/[^A-Za-z0-9]/.test(pw)) sc++
  return Math.max(1, Math.min(4, Math.round((sc * 4) / 5)))
}

/**
 * 분류 meta(원본 컨텍스트·근처 URL·미분류 코드)에서 memo 자동 채움용 텍스트를 만든다.
 * "라벨: 값" 조각을 " · "로 이어붙인다 — memo가 단일 줄 input이라 줄바꿈(\n)은 브라우저가
 * 지워버리므로 쓰지 않는다. 사용자가 직접 지우거나 고치면 그 상태 그대로 저장된다(자동 재삽입 없음).
 */
export function autoMemoFrom(meta: Record<string, unknown> | undefined): string {
  if (!meta) return ''
  const parts: string[] = []
  const context = meta['context']
  if (typeof context === 'string' && context) parts.push(`원본: ${context}`)
  const urls = meta['nearby_urls']
  if (Array.isArray(urls) && urls.length) parts.push(`관련 링크: ${urls.join(', ')}`)
  const codes = meta['nearby_codes']
  if (Array.isArray(codes) && codes.length) parts.push(`근처 미분류 코드: ${codes.join(', ')}`)
  return parts.join(' · ')
}

/** 보관함 항목들을 .env 텍스트로 직렬화(서비스별 그룹, 주석에 컬렉션). */
export function envText(items: VaultItem[]): string {
  const out: string[] = []
  SERVICE_ORDER.forEach((name) => {
    const its = items.filter((i) => i.service === name)
    if (!its.length) return
    out.push('# ' + name)
    its.forEach((i) =>
      out.push(i.varName + '=' + i.full + (i.project ? '  # ' + i.project : '')),
    )
    out.push('')
  })
  return out.join('\n').trim()
}

/**
 * 값 마스킹 - 앞부분(접두어 식별용)과 뒤 4자만 남기고 가린다.
 * backend/app/masking.py 의 mask() 와 같은 규칙이다. .env 가져오기는 값이 프론트에만
 * 존재해 백엔드 마스킹을 쓸 수 없어서 여기에 같은 로직을 둔다.
 *
 * keepFront 는 공개 정보인 접두어(sk- 등)를 식별용으로 남기기 위한 값이다.
 * 12자 미만의 짧은 값은 부분 노출만으로도 복원 여지가 커 전체를 가린다.
 */
export function mask(value: string, keepFront = 8, keepBack = 4): string {
  const n = value.length
  if (n < 12) return BULLET.repeat(n)
  const front = Math.min(keepFront, Math.max(1, n - keepBack - 4))
  const hidden = Math.min(16, Math.max(4, n - front - keepBack))
  return value.slice(0, front) + BULLET.repeat(hidden) + value.slice(-keepBack)
}
