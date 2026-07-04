// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * OCR 재구성/페어링 테스트 (CORE-3 난이도 핵심). 모든 값은 더미.
 * 실제 tesseract.js 없이 word-box 픽스처로 공간 로직만 검증한다.
 */
import { describe, expect, it } from 'vitest'
import { groupRows, isMasked, reconstruct, reconstructText, type OcrWord } from './reconstruct'

/** (text, x, y) → 대략적 word box. 높이 20px, 너비는 글자수 비례로 픽스처를 간결히. */
function w(text: string, x: number, y: number): OcrWord {
  return { text, bbox: { x0: x, y0: y, x1: x + text.length * 9, y1: y + 20 } }
}

describe('groupRows', () => {
  it('세로 중심이 가까운 단어는 같은 행, 좌→우 정렬', () => {
    const rows = groupRows([w('ID', 200, 100), w('Database', 100, 102)])
    expect(rows).toHaveLength(1)
    expect(rows[0].map((x) => x.text)).toEqual(['Database', 'ID'])
  })

  it('세로로 떨어진 단어는 다른 행, 위→아래 정렬', () => {
    const rows = groupRows([w('below', 100, 140), w('above', 100, 100)])
    expect(rows.map((r) => r[0].text)).toEqual(['above', 'below'])
  })
})

describe('isMasked', () => {
  it('연속 마스킹 글리프 → 마스킹', () => {
    expect(isMasked('secret_••••')).toBe(true)
    expect(isMasked('●●●●●●')).toBe(true)
  })
  it('정상 값 → 마스킹 아님', () => {
    expect(isMasked('a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6')).toBe(false)
    expect(isMasked('sk-proj-abcdef')).toBe(false)
  })
})

describe('reconstructText', () => {
  it('라벨(윗줄) + 값(아랫줄) 관계를 줄 구조로 보존 → Stage2 페어링 입력', () => {
    // Notion 통합 설정: "Database ID" 라벨 위, 값 아래.
    const words = [
      w('Database', 100, 100),
      w('ID', 190, 100),
      w('3f9a1c2e7b4d4e8a9c1f2d5e8a7b4c3f', 100, 130),
    ]
    expect(reconstructText(words)).toBe(
      'Database ID\n3f9a1c2e7b4d4e8a9c1f2d5e8a7b4c3f',
    )
  })

  it('마스킹된 값 → [마스킹됨] 자리표시자(가짜 값 생성 금지, CORE-3 AC)', () => {
    const words = [w('Secret', 100, 100), w('secret_••••••••', 100, 130)]
    expect(reconstructText(words)).toBe('Secret\n[마스킹됨]')
  })

  it('복사/표시 버튼 등 UI 잡음 제거', () => {
    const words = [
      w('REST', 100, 100),
      w('API', 150, 100),
      w('키', 190, 100),
      w('a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6', 100, 130),
      w('복사', 400, 130), // 값 옆 복사 버튼
    ]
    expect(reconstructText(words)).toBe(
      'REST API 키\na1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6',
    )
  })

  it('구두점에서 쪼개진 토큰을 간격으로 재결합(실측: 6789. Dumm → 6789.Dumm)', () => {
    // OCR 이 `<hex>.<suffix>` 를 점 뒤에서 둘로 나눈 상황 — 두 박스가 촘촘히 붙어 있음.
    const a = { text: 'abcdef0123456789abcdef0123456789.', bbox: { x0: 100, y0: 100, x1: 420, y1: 122 } }
    const b = { text: 'DummyOllamaSuffixi234567', bbox: { x0: 423, y0: 100, x1: 640, y1: 122 } }
    // 가까운 간격(3px ≪ 글자폭) → 공백 없이 결합.
    expect(reconstructText([a, b])).toBe(
      'abcdef0123456789abcdef0123456789.DummyOllamaSuffixi234567',
    )
  })

  it('정상 단어 간격은 공백으로 유지(과결합 방지)', () => {
    // "Database"(x1=190) 와 "ID"(x0=210) 사이 20px 는 글자폭 대비 충분 → 공백 유지.
    expect(reconstructText([w('Database', 100, 100), w('ID', 210, 100)])).toBe('Database ID')
  })

  it('이어붙인 이음매 위치를 flagged 로 남긴다(값 확인 표식용)', () => {
    const a = { text: 'abcdef0123456789abcdef0123456789.', bbox: { x0: 100, y0: 100, x1: 420, y1: 122 } }
    const b = { text: 'DummyOllamaSuffixi234567', bbox: { x0: 423, y0: 100, x1: 640, y1: 122 } }
    const rec = reconstruct([a, b])
    expect(rec.flagged).toHaveLength(1)
    expect(rec.flagged[0].text).toBe(rec.text)
    expect(rec.flagged[0].marks).toEqual([33]) // 첫 토큰 길이 = 두 번째 토큰 시작 위치
  })

  it('정상 간격만 있으면 flagged 는 비어있다', () => {
    expect(reconstruct([w('Database', 100, 100), w('ID', 210, 100)]).flagged).toEqual([])
  })

  it('한글/영문 라벨 혼재 여러 키를 각 줄로 보존(카카오 다중 키 화면)', () => {
    const words = [
      w('REST', 100, 100),
      w('API', 150, 100),
      w('키', 190, 100),
      w('11111111111111111111111111111111', 100, 130),
      w('JavaScript', 100, 200),
      w('키', 200, 200),
      w('22222222222222222222222222222222', 100, 230),
    ]
    expect(reconstructText(words)).toBe(
      'REST API 키\n11111111111111111111111111111111\nJavaScript 키\n22222222222222222222222222222222',
    )
  })
})
