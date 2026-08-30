// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * `.env` 텍스트를 {이름, 값} 목록으로 읽는다. 순수 함수 - 부수효과 없음.
 *
 * 왜 프론트에 파서를 두나: 백엔드 /analyze 는 값 기준으로 중복을 제거한다. .env 에서
 * 두 변수가 같은 값을 갖는 건 흔한데(DATABASE_URL / DB_URL), 그러면 변수 하나가 조용히
 * 사라진다. 그래서 이름·값의 권위 있는 목록은 여기서 만들고, /analyze 결과는 분류
 * 정보를 얹는 보강용으로만 쓴다.
 *
 * 지원 범위는 백엔드 파서(stage1)와 맞췄다. 여러 줄 값은 지원하지 않는다 - 시크릿에는
 * 사실상 안 쓰이고, 지원하면 파서가 훨씬 복잡해진다.
 */

export interface ParsedEnvVar {
  name: string
  value: string
}

/** 환경변수 이름으로 인정할 형태(POSIX 관례). */
const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/

/**
 * 값에서 따옴표를 벗기고 인라인 주석을 잘라낸다.
 * 따옴표로 감싼 값은 그 안의 `#` 을 주석으로 보지 않는다.
 */
function cleanValue(raw: string): string {
  const trimmed = raw.trim()
  const quote = trimmed[0]
  if (quote === '"' || quote === "'") {
    const end = trimmed.indexOf(quote, 1)
    if (end > 0) return trimmed.slice(1, end)
    return trimmed.slice(1) // 닫는 따옴표가 없으면 나머지를 값으로 본다
  }
  const hash = trimmed.indexOf('#')
  return (hash >= 0 ? trimmed.slice(0, hash) : trimmed).trim()
}

export function parseEnv(text: string): ParsedEnvVar[] {
  const byName = new Map<string, string>()
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue

    const eq = line.indexOf('=')
    if (eq <= 0) continue

    let name = line.slice(0, eq).trim()
    if (name.startsWith('export ')) name = name.slice('export '.length).trim()
    if (!NAME_RE.test(name)) continue

    const value = cleanValue(line.slice(eq + 1))
    if (!value) continue

    byName.set(name, value) // 같은 이름이 또 나오면 나중 줄이 이긴다(.env 관례)
  }
  return [...byName].map(([name, value]) => ({ name, value }))
}
