// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/cn'

/**
 * 더블클릭하면 그 자리에서 고칠 수 있는 텍스트. 편집 중임이 눈에 띄도록 테두리를 진하게
 * 하고 커서를 그 칸에 둔다(자동 포커스 + 전체 선택).
 *
 * Enter 또는 포커스가 빠지면 확정, Escape 면 되돌린다. 키보드만으로도 쓸 수 있게
 * Enter 로도 편집에 들어갈 수 있다(더블클릭은 마우스 사용자용 지름길).
 */
export function InlineEdit({
  value,
  onCommit,
  displayValue,
  placeholder,
  mono = false,
  ariaLabel,
}: {
  value: string
  onCommit: (next: string) => void
  /** 편집 중이 아닐 때 대신 보여줄 문자열(마스킹 등). 없으면 value 를 그대로 보여준다. */
  displayValue?: string
  placeholder?: string
  mono?: boolean
  ariaLabel: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) {
      ref.current?.focus()
      ref.current?.select()
    }
  }, [editing])

  // 바깥에서 값이 바뀌면(예: 제안 적용) 편집 중이 아닐 때 따라간다.
  useEffect(() => {
    if (!editing) setDraft(value)
  }, [value, editing])

  const commit = () => {
    setEditing(false)
    const next = draft.trim()
    if (next !== value) onCommit(next)
  }

  if (editing) {
    return (
      <input
        ref={ref}
        value={draft}
        aria-label={ariaLabel}
        // 편집 중임을 DOM 에 표시한다. Modal 이 이걸 보고 Escape 로 다이얼로그가 닫히는 걸
        // 막는다 - Radix DismissableLayer 는 document 에 capture 로 붙어 있어서, 아래
        // onKeyDown 의 stopPropagation 만으로는 이미 늦다(리액트 버블 핸들러가 나중에 돈다).
        data-inline-editing="true"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          // capture 로 듣지 않는 바깥 핸들러(중첩 폼 등)까지는 여기서 막아 둔다.
          if (e.key === 'Enter') {
            e.stopPropagation()
            commit()
          }
          if (e.key === 'Escape') {
            e.stopPropagation()
            setDraft(value)
            setEditing(false)
          }
        }}
        className={cn(
          'w-full rounded-md bg-surface px-2 py-1 text-[12.5px] text-fg outline-none',
          // 편집 중임을 분명히 - 테두리를 진하게, 링까지
          'border-2 border-[rgba(62,207,142,.75)] ring-2 ring-[rgba(62,207,142,.18)]',
          mono && 'font-mono',
        )}
      />
    )
  }

  return (
    <button
      type="button"
      aria-label={ariaLabel}
      title="더블클릭하면 고칠 수 있어요"
      onDoubleClick={() => setEditing(true)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') setEditing(true)
      }}
      className={cn(
        'w-full cursor-text rounded-md border-2 border-transparent px-2 py-1 text-left',
        'text-[12.5px] text-fg hover:border-border-strong hover:bg-surface',
        mono && 'font-mono',
        !value && 'text-faint-2',
      )}
    >
      {/* ?? 가 아니라 || - mask('') 처럼 빈 문자열이 오면 placeholder 로 넘겨야
          칸이 아예 안 보여 누를 수 없게 되는 걸 막는다. */}
      {displayValue || value || ''}
      {!value && !displayValue && (placeholder || '')}
    </button>
  )
}
