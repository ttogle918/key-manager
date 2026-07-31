// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { describe, expect, it } from 'vitest'
import { matchCandidates, splitKeyValue } from './autocomplete'

describe('splitKeyValue', () => {
  it('NAME=VALUE를 이름/값으로 분리한다', () => {
    expect(splitKeyValue('OPENAI_API_KEY=sk-abc123')).toEqual({
      name: 'OPENAI_API_KEY',
      value: 'sk-abc123',
    })
  })

  it('맨 앞 $ 기호는 제거한다', () => {
    expect(splitKeyValue('$OPENAI_API_KEY=sk-abc123')).toEqual({
      name: 'OPENAI_API_KEY',
      value: 'sk-abc123',
    })
  })

  it('양쪽 공백은 trim한다', () => {
    expect(splitKeyValue('  OPENAI_API_KEY = sk-abc123  ')).toEqual({
      name: 'OPENAI_API_KEY',
      value: 'sk-abc123',
    })
  })

  it('값에 =가 또 있어도 첫 번째 =만 구분자로 쓴다', () => {
    expect(splitKeyValue('CONN_STRING=host=localhost;port=5432')).toEqual({
      name: 'CONN_STRING',
      value: 'host=localhost;port=5432',
    })
  })

  it('=가 없으면 null', () => {
    expect(splitKeyValue('OPENAI_API_KEY')).toBeNull()
  })

  it('이름이 비면(=로 시작) null', () => {
    expect(splitKeyValue('=sk-abc123')).toBeNull()
  })
})

describe('matchCandidates', () => {
  const candidates = [
    'OPENAI_API_KEY',
    'OPENAI_ORG_ID',
    'NOTION_API_KEY',
    'GITHUB_TOKEN',
    'openai_api_key', // 대소문자만 다른 중복
  ]

  it('접두어로 시작하는 후보만, 대소문자 무시로 반환한다', () => {
    expect(matchCandidates(candidates, 'ope')).toEqual(['OPENAI_API_KEY', 'OPENAI_ORG_ID'])
  })

  it('중복은 하나로 합친다', () => {
    const result = matchCandidates(candidates, 'OPENAI_API')
    expect(result).toEqual(['OPENAI_API_KEY'])
  })

  it('알파벳순으로 정렬한다', () => {
    expect(matchCandidates(candidates, 'OPENAI')).toEqual(['OPENAI_API_KEY', 'OPENAI_ORG_ID'])
  })

  it('접두어가 비어 있으면 빈 배열(전체 목록을 뱉지 않는다)', () => {
    expect(matchCandidates(candidates, '')).toEqual([])
  })

  it('일치하는 후보가 없으면 빈 배열', () => {
    expect(matchCandidates(candidates, 'ZZZ')).toEqual([])
  })
})
