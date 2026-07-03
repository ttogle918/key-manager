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
