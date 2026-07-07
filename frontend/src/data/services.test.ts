// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 서비스 레지스트리 테스트 — `/knowledge` 응답으로 종류맵이 동적 구성되는지 검증.
 * 핵심: 새 서비스는 YAML(→ /knowledge) 하나로 프론트에 자동 반영된다(코드 수정 0).
 */
import { describe, expect, it } from 'vitest'
import type { KnowledgeResponse } from '@/api/types'
import * as reg from './services'

function cred(kind: string, label: string, env: string) {
  return { kind, label, official_env_name: env, value_based: false, expiry_known: false, verifiable: false }
}

const PAYLOAD: KnowledgeResponse = {
  services: [
    // 일부러 알파벳 역순으로 넣어 정렬 로직을 검증
    { service: 'openai', display_name: 'OpenAI', credentials: [cred('api_key', 'API Key', 'OPENAI_API_KEY')] },
    { service: 'notion', display_name: 'Notion', credentials: [
      cred('api_key', 'API Key', 'NOTION_API_KEY'),
      cred('database_id', 'Database ID', 'NOTION_DATABASE_ID'),
    ] },
    // 큐레이션에 없는 새 서비스 2종(자동 외양·알파벳 정렬 대상)
    { service: 'stripe', display_name: 'Stripe', credentials: [cred('secret_key', 'Secret Key', 'STRIPE_SECRET_KEY')] },
    { service: 'github', display_name: 'GitHub', credentials: [cred('pat', 'Personal Access Token', 'GITHUB_TOKEN')] },
  ],
}

describe('applyKnowledge', () => {
  it('TYPE_MAP을 kind=typeKey, official_env_name=var로 구성한다', () => {
    reg.applyKnowledge(PAYLOAD)
    expect(reg.TYPE_MAP['Notion']).toMatchObject([
      { v: 'api_key', label: 'API Key', var: 'NOTION_API_KEY' },
      { v: 'database_id', label: 'Database ID', var: 'NOTION_DATABASE_ID' },
    ])
  })

  it('id ↔ 표시명 맵을 양방향으로 만든다', () => {
    reg.applyKnowledge(PAYLOAD)
    expect(reg.SERVICE_TO_ID['GitHub']).toBe('github')
    expect(reg.SERVICE_BY_ID['github']).toBe('GitHub')
  })

  it('큐레이션 서비스를 앞에(정해진 순서), 새 서비스는 뒤에 알파벳순으로 정렬한다', () => {
    reg.applyKnowledge(PAYLOAD)
    // notion·openai(큐레이션 순서) 먼저, 그 뒤 GitHub·Stripe(알파벳)
    expect(reg.SERVICE_ORDER).toEqual(['Notion', 'OpenAI', 'GitHub', 'Stripe'])
  })

  it('알려진 서비스는 큐레이션 외양을 유지한다', () => {
    reg.applyKnowledge(PAYLOAD)
    expect(reg.SVC_META['Notion']).toEqual({ tile: 'N', bg: '#E7EAEE', fg: '#15181D' })
  })

  it('새 서비스는 코드 수정 없이 자동으로 타일·색을 부여받는다', () => {
    reg.applyKnowledge(PAYLOAD)
    const gh = reg.SVC_META['GitHub']
    expect(gh.tile).toBe('Gi') // 표시명 앞 2글자
    expect(gh.bg).toMatch(/^#[0-9A-F]{6}$/i) // 팔레트에서 결정적으로 배정
    expect(gh.fg).toBe('#FFFFFF')
    // 새 서비스의 종류도 그대로 노출된다(프론트 하드코딩 없이)
    expect(reg.TYPE_MAP['GitHub']).toMatchObject([
      { v: 'pat', label: 'Personal Access Token', var: 'GITHUB_TOKEN' },
    ])
  })

  it('발급 도움말(GUIDE-1)을 종류·서비스 단위로 싣는다', () => {
    reg.applyKnowledge({
      services: [
        {
          service: 'demo',
          display_name: 'Demo',
          console_url: 'https://demo.example/console',
          steps: ['1단계', '2단계'],
          prereq: '앱 먼저 생성',
          credentials: [
            {
              ...cred('api_key', 'API Key', 'DEMO_API_KEY'),
              role: '서버 전용 비밀 키',
              issue_url: 'https://demo.example/keys',
              docs_url: 'https://demo.example/docs',
            },
          ],
        },
      ],
    })
    const t = reg.TYPE_MAP['Demo'][0]
    expect(t.role).toBe('서버 전용 비밀 키')
    expect(t.issueUrl).toBe('https://demo.example/keys')
    expect(t.docsUrl).toBe('https://demo.example/docs')
    expect(reg.CONSOLE_URL['Demo']).toBe('https://demo.example/console')
    expect(reg.SVC_STEPS['Demo']).toEqual(['1단계', '2단계'])
    expect(reg.SVC_PREREQ['Demo']).toBe('앱 먼저 생성')
  })

  it('딥링크(GUIDE-1 B): ID면 치환·아니면 폴백·화이트리스트 강제', () => {
    reg.applyKnowledge({
      services: [
        {
          service: 'gcp',
          display_name: 'GCP',
          console_url: 'https://console.cloud.google.com/apis/credentials?project={project}',
          credentials: [
            { ...cred('api_key', 'API Key', 'GOOGLE_API_KEY'), docs_url: 'https://cloud.google.com/docs' },
          ],
        },
      ],
    })
    const base = 'https://console.cloud.google.com/apis/credentials?project={project}'
    // ID 형태 → 치환(딥링크)
    expect(reg.resolveIssueUrl(base, 'my-proj-123')).toBe(
      'https://console.cloud.google.com/apis/credentials?project=my-proj-123',
    )
    // 한글·공백 라벨 → 치환 안 함, 플레이스홀더 쿼리 제거(기본 콘솔)
    expect(reg.resolveIssueUrl(base, '블로그 자동화')).toBe(
      'https://console.cloud.google.com/apis/credentials',
    )
    // 값 없어도 안전 폴백
    expect(reg.resolveIssueUrl(base, null)).toBe(
      'https://console.cloud.google.com/apis/credentials',
    )
    // 화이트리스트: 선언 호스트·https 만
    expect(reg.isAllowedUrl('https://console.cloud.google.com/x')).toBe(true)
    expect(reg.isAllowedUrl('https://cloud.google.com/docs')).toBe(true)
    expect(reg.isAllowedUrl('https://evil.example/x')).toBe(false)
    expect(reg.isAllowedUrl('http://console.cloud.google.com/x')).toBe(false)
    expect(reg.isAllowedUrl('javascript:alert(1)')).toBe(false)
    // 미선언 호스트 URL 은 resolveIssueUrl 도 null
    expect(reg.resolveIssueUrl('https://evil.example/x', 'id')).toBeNull()
  })
})
