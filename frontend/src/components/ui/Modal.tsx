// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import * as Dialog from '@radix-ui/react-dialog'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface ModalProps {
  open: boolean
  onClose: () => void
  /** 접근성용 제목 — 화면에는 숨기고 스크린리더에만 노출(가시 제목은 children에 둠). */
  title: string
  className?: string
  children: ReactNode
}

/**
 * Radix Dialog 기반 모달. 포커스 트랩·ESC 닫기·aria 속성을 무료로 얻는다.
 * 프로토타입의 고정 오버레이 + 중앙 패널 스타일을 재현한다.
 */
export function Modal({ open, onClose, title, className, children }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[80] bg-[rgba(4,6,8,.72)] [animation:klFade_.15s]" />
        <Dialog.Content
          aria-describedby={undefined}
          // 인라인 편집 중의 Escape 는 "편집 취소"지 "모달 닫기"가 아니다. Radix 는 document 에
          // capture 로 붙어 있어 자식에서 stopPropagation 해도 못 막으므로, 여기서 편집 중인
          // 입력칸에서 온 Escape 를 걸러낸다. 안 걸러내면 값 하나 고치다 취소했을 뿐인데
          // .env 가져오기 표가 통째로 사라진다.
          onEscapeKeyDown={(e) => {
            const target = e.target as HTMLElement | null
            if (target?.closest?.('[data-inline-editing="true"]')) e.preventDefault()
          }}
          className={cn(
            'fixed left-1/2 top-1/2 z-[90] -translate-x-1/2 -translate-y-1/2',
            'rounded-xl border border-border bg-elevated p-5 shadow-[0_20px_50px_rgba(0,0,0,.5)]',
            'focus:outline-none [animation:klFadeUp_.18s_ease]',
            className,
          )}
        >
          <Dialog.Title className="sr-only">{title}</Dialog.Title>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
