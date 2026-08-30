// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * .env 파서 테스트.
 *
 * 가장 중요한 케이스는 "같은 값 다른 이름" 이다 - 백엔드 /analyze 는 값 기준으로 중복을
 * 제거해서 두 변수 중 하나를 조용히 버린다. 이 파서를 따로 두는 이유가 그것이고,
 * 회귀하면 사용자의 변수가 소리 없이 사라진다.
 */
import { describe, expect, it } from 'vitest'
import { parseEnv } from './envParse'

const GH = 'ghp_aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpP1234'

describe('parseEnv', () => {
  it('기본 KEY=VALUE 를 읽는다', () => {
    expect(parseEnv(`FOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('쌍따옴표와 홑따옴표를 벗긴다', () => {
    expect(parseEnv(`A="${GH}"\nB='${GH}'`)).toEqual([
      { name: 'A', value: GH },
      { name: 'B', value: GH },
    ])
  })

  it('export 접두어를 제거한다', () => {
    expect(parseEnv(`export FOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('= 주변 공백을 무시한다', () => {
    expect(parseEnv(`FOO = ${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('인라인 주석을 잘라낸다', () => {
    expect(parseEnv(`FOO=${GH}  # 발급용 메모`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('주석줄과 빈 줄을 건너뛴다', () => {
    expect(parseEnv(`# 주석\n\n   \nFOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('빈 값과 이름 없는 줄을 건너뛴다', () => {
    expect(parseEnv(`EMPTY=\n=${GH}\nFOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('같은 값을 가진 다른 이름 두 줄을 모두 남긴다', () => {
    expect(parseEnv(`FOO=${GH}\nBAR=${GH}`)).toEqual([
      { name: 'FOO', value: GH },
      { name: 'BAR', value: GH },
    ])
  })

  it('같은 이름이 두 번 나오면 나중 줄이 이긴다(.env 관례)', () => {
    expect(parseEnv(`FOO=first\nFOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('따옴표 안의 # 는 주석으로 보지 않는다', () => {
    expect(parseEnv(`FOO="abc#def"`)).toEqual([{ name: 'FOO', value: 'abc#def' }])
  })

  it('여러 줄 값은 첫 줄만 잡는다(문서화된 한계)', () => {
    expect(parseEnv(`FOO="line1\nline2"`)).toEqual([{ name: 'FOO', value: 'line1' }])
  })

  it('CRLF 줄바꿈을 처리한다', () => {
    expect(parseEnv(`FOO=${GH}\r\nBAR=x`)).toEqual([
      { name: 'FOO', value: GH },
      { name: 'BAR', value: 'x' },
    ])
  })

  it('환경변수 이름 형식이 아니면 건너뛴다', () => {
    expect(parseEnv(`나쁜 이름=${GH}\nFOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('빈 텍스트는 빈 배열', () => {
    expect(parseEnv('')).toEqual([])
  })
})
