// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 보관함 항목을 **2초간 누르고 있으면** 들어올려 다른 서비스 그룹으로 옮기는 드래그.
 *
 * 이건 어디까지나 **지름길**이다. 정확한 이동 경로는 상세보기의 "서비스" 드롭다운이고,
 * 그쪽이 키보드·터치·스크린리더에서 유일하게 확실한 경로다. 드래그만 두면 마우스가
 * 없는 사용자에게 기능이 통째로 막힌다.
 *
 * 왜 2초 지연이 필요한가: 보관함 행은 클릭(값 공개)·더블클릭(회전)이 이미 걸려 있다.
 * 지연 없이 드래그를 붙이면 값을 보려고 누른 것이 드래그로 오인된다. dnd-kit 의
 * `activationConstraint` 로 "누르고 있어야 시작"을 만든다.
 */
import { useDraggable, useDroppable } from '@dnd-kit/core'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { dropZoneId } from './dndIds'

/** 한 항목을 감싸 드래그 가능하게 만든다. */
export function DraggableItem({
  id,
  children,
}: {
  id: string
  children: ReactNode
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id })
  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      // 들어올린 항목은 자리를 지키되 흐리게 - 원래 어디 있었는지 보여야 되돌리기 쉽다.
      className={cn(isDragging && 'opacity-40')}
    >
      {children}
    </div>
  )
}

/** 서비스 그룹 헤더를 드롭 대상으로 만든다. */
export function DropZone({
  serviceName,
  active,
  children,
}: {
  serviceName: string
  /** 드래그가 진행 중일 때만 대상임을 시각적으로 알린다. */
  active: boolean
  children: ReactNode
}) {
  const { setNodeRef, isOver } = useDroppable({ id: dropZoneId(serviceName) })
  return (
    <div
      ref={setNodeRef}
      className={cn(
        'transition-colors',
        active && 'outline-dashed outline-1 outline-offset-[-2px] outline-[rgba(62,207,142,.35)]',
        isOver && 'bg-[rgba(62,207,142,.10)] outline-[rgba(62,207,142,.9)]',
      )}
    >
      {children}
    </div>
  )
}

/**
 * 드래그 중에만 나타나는 "여기로 옮기기" 자리.
 *
 * 보관함은 항목이 있는 서비스 그룹만 그린다. 그래서 이게 없으면 **그 컬렉션에 아직
 * 없는 서비스로는 아예 옮길 수 없다** - 미지정 항목을 PostgreSQL 로 옮기는 것이
 * 정확히 그 경우다.
 */
export function EmptyDropZone({ serviceName, tile }: { serviceName: string; tile?: string }) {
  const { setNodeRef, isOver } = useDroppable({ id: dropZoneId(serviceName) })
  return (
    <div
      ref={setNodeRef}
      className={cn(
        'mx-4 my-[6px] flex items-center gap-[8px] rounded-[8px] border border-dashed px-3 py-[10px] text-[11.5px] transition-colors',
        isOver
          ? 'border-[rgba(62,207,142,.9)] bg-[rgba(62,207,142,.12)] text-fg-soft'
          : 'border-line-2 text-faint',
      )}
    >
      <span className="font-mono text-[10px]">{tile ?? '?'}</span>
      <span>{serviceName} 로 옮기기</span>
    </div>
  )
}
