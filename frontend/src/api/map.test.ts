// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * `metaToVaultItem` 의 서비스 판정 테스트.
 *
 * 여기가 회귀하면 사용자에게 **틀린 벤더**가 보인다. 원래 이 함수는 분류가 안 된 항목
 * (백엔드가 service=null 로 저장한 것)을 'OpenAI'로 떨어뜨렸고, `.env` 가져오기가
 * 분류 불가한 줄(DB_HOST 등)까지 전부 가져오면서 그 항목들이 죄다 OpenAI 밑에 쌓였다.
 * 모르면 모른다고 표시해야 한다.
 */
import { describe, expect, it } from 'vitest'
import { metaToVaultItem } from './map'
import { SERVICE_BY_ID, UNCLASSIFIED_SERVICE } from '@/data/services'
import type { VaultEntryMeta } from './types'

/** 필수 필드만 채운 최소 메타. 각 테스트에서 필요한 것만 덮어쓴다. */
function meta(over: Partial<VaultEntryMeta> = {}): VaultEntryMeta {
  return { id: 1, created_at: '2026-08-31T00:00:00Z', ...over }
}

describe('metaToVaultItem 의 서비스 판정', () => {
  it('분류된 항목은 그 서비스로 간다', () => {
    // 부트스트랩 레지스트리에 있는 id 를 쓴다(지식베이스 로드 전에도 성립해야 한다).
    expect(SERVICE_BY_ID['notion']).toBe('Notion')
    expect(metaToVaultItem(meta({ service: 'notion' })).service).toBe('Notion')
  })

  it('service 가 null 이면 OpenAI 가 아니라 미지정으로 간다', () => {
    expect(metaToVaultItem(meta({ service: null })).service).toBe(UNCLASSIFIED_SERVICE)
  })

  it('service 필드가 아예 없어도 미지정으로 간다', () => {
    expect(metaToVaultItem(meta()).service).toBe(UNCLASSIFIED_SERVICE)
  })

  it('빈 문자열 service 도 미지정으로 간다', () => {
    expect(metaToVaultItem(meta({ service: '' })).service).toBe(UNCLASSIFIED_SERVICE)
  })

  it('모르는 service id 를 특정 벤더로 둔갑시키지 않는다', () => {
    // 지식베이스에서 서비스가 빠졌거나 오래된 금고를 열었을 때의 경로다.
    expect(metaToVaultItem(meta({ service: 'nonexistent_vendor' })).service).toBe(
      UNCLASSIFIED_SERVICE,
    )
  })

  it('미지정이어도 이름·컬렉션 등 나머지 필드는 그대로 보존한다', () => {
    const it_ = metaToVaultItem(
      meta({ service: null, official_name: 'DB_HOST', project: 'my-blog', label: '호스트' }),
    )
    expect(it_.service).toBe(UNCLASSIFIED_SERVICE)
    expect(it_.varName).toBe('DB_HOST')
    expect(it_.project).toBe('my-blog')
    expect(it_.type).toBe('호스트')
  })
})
