// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 보관함 드래그의 상수와 드롭 대상 id 규칙. 컴포넌트 파일에서 분리해 둔다
 * (같이 두면 Fast Refresh 가 동작하지 않는다).
 */

/** 드래그 활성화까지 눌러야 하는 시간(ms). 짧게 하면 클릭(값 공개)과 충돌한다. */
export const DRAG_HOLD_MS = 2000

/**
 * 지연 대기 중 허용되는 손떨림(px). dnd-kit 의 DelayConstraint 에서 tolerance 는
 * **선택이 아니라 필수**다 - 빼면 조금만 움직여도 활성화가 취소된다.
 */
export const DRAG_TOLERANCE_PX = 8

/** 드롭 대상 id 를 서비스 표시명으로부터 만든다(미지정 포함). */
export function dropZoneId(serviceName: string): string {
  return `svc:${serviceName}`
}

export function serviceFromDropZoneId(id: string): string | null {
  return id.startsWith('svc:') ? id.slice(4) : null
}
