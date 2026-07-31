// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 직접 입력 탭 전용 유틸 — "NAME=VALUE" 붙여넣기 분리 + cmd/셸 스타일 Tab 자동완성.
 * 상태(순환 인덱스 등)는 여기 두지 않는다 — 컴포넌트의 로컬 상태로 관리한다(전역 스토어에 둘
 * 만큼 공유되는 값이 아님).
 */

/** "$NAME=VALUE" 또는 "NAME=VALUE"를 이름/값으로 분리. `=`가 없거나 이름이 비면 null. */
export function splitKeyValue(text: string): { name: string; value: string } | null {
  const idx = text.indexOf('=')
  if (idx < 0) return null
  const name = text.slice(0, idx).trim().replace(/^\$/, '')
  const value = text.slice(idx + 1).trim()
  if (!name) return null
  return { name, value }
}

/**
 * prefix로 시작하는 후보를 대소문자 무시로 찾아 알파벳순 정렬(중복 제거).
 * prefix가 비어 있으면 아무것도 제안하지 않는다(모든 후보가 뜨는 건 자동완성이 아니라 목록이다).
 */
export function matchCandidates(candidates: string[], prefix: string): string[] {
  if (!prefix) return []
  const lower = prefix.toLowerCase()
  const seen = new Map<string, string>() // 소문자 키 → 먼저 나온 표기(대소문자만 다른 중복 제거)
  for (const c of candidates) {
    const key = c.toLowerCase()
    if (key.startsWith(lower) && !seen.has(key)) seen.set(key, c)
  }
  return Array.from(seen.values()).sort((a, b) => a.localeCompare(b))
}
