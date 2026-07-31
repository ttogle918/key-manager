// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useState } from 'react'
import { matchCandidates } from '@/lib/autocomplete'

interface Props {
  value: string
  onChange: (v: string) => void
  onEnter?: () => void
  candidates: string[]
  placeholder?: string
}

/** 입력 칸과 고스트(연한색 제안) 오버레이가 픽셀 단위로 겹치도록 두 요소가 공유하는 박스 스타일. */
const BOX =
  'w-full rounded-lg px-3 py-[10px] font-mono text-[12.5px] leading-[1.4] whitespace-pre'

interface CycleState {
  matches: string[]
  index: number
}

/**
 * cmd/셸 스타일 Tab 자동완성 입력 — 접두어를 타이핑하면 첫 후보의 나머지를 연한 색으로 미리
 * 보여주고(고스트 텍스트), Tab을 누르면 채워지며, 연속으로 Tab을 누르면 같은 접두어의 다음
 * 후보로 순환한다. 순환 상태는 이 컴포넌트에만 필요한 휘발성 상태라 전역 스토어에 두지 않는다.
 */
export function AutocompleteNameInput({ value, onChange, onEnter, candidates, placeholder }: Props) {
  const [cycle, setCycle] = useState<CycleState | null>(null)

  const ghost = (() => {
    if (!value) return ''
    const matches = matchCandidates(candidates, value)
    if (!matches.length) return ''
    const first = matches[0]
    return first.slice(value.length)
  })()

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Tab') {
      e.preventDefault()
      // 직전 Tab이 채워 넣은 값 그대로면(추가 타이핑 없었음) 같은 순환에서 다음 후보로.
      if (cycle && cycle.matches[cycle.index] === value) {
        const next = (cycle.index + 1) % cycle.matches.length
        onChange(cycle.matches[next])
        setCycle({ matches: cycle.matches, index: next })
        return
      }
      const matches = matchCandidates(candidates, value)
      if (matches.length) {
        onChange(matches[0])
        setCycle({ matches, index: 0 })
      }
      return
    }
    if (e.key === 'Enter') {
      onEnter?.()
      return
    }
    // 다른 키 입력은 새 타이핑으로 보고 순환을 리셋한다.
    if (cycle) setCycle(null)
  }

  return (
    <div className="relative">
      {/* 배경·테두리는 항상 이 아래쪽 레이어가 담당한다 — 위의 실제 input은 배경을 투명하게
          둬서, 그 밑에 깔린 고스트 텍스트(연한색 제안)가 가려지지 않고 비치게 한다. */}
      <div
        aria-hidden="true"
        className={`${BOX} pointer-events-none absolute inset-0 overflow-hidden border border-border bg-surface text-fg`}
      >
        <span className="invisible">{value}</span>
        {ghost && <span className="text-dim-2">{ghost}</span>}
      </div>
      <input
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setCycle(null)
        }}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        className={`${BOX} relative border border-transparent bg-transparent text-fg outline-none focus:border-[rgba(62,207,142,.55)]`}
      />
    </div>
  )
}
