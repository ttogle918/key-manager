// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 보관함 드래그의 상수와 드롭 대상 id 규칙. 컴포넌트 파일에서 분리해 둔다
 * (같이 두면 Fast Refresh 가 동작하지 않는다).
 */

/**
 * 드래그 활성화까지 눌러야 하는 시간(ms).
 *
 * 클릭(값 공개)·더블클릭(회전)과 충돌하지 않을 만큼은 길어야 하지만, 처음 2000ms 로
 * 뒀더니 "눌러도 반응이 없다"는 인상을 줬다. 보통의 클릭은 100~200ms 만에 손을 떼고
 * 더블클릭도 짧은 누름 두 번이라 이 타이머에 닿지 않으므로 600ms 로도 충분히 안전하다.
 */
export const DRAG_HOLD_MS = 600

/**
 * 지연 대기 중 허용되는 포인터 이동(px). 이 거리를 넘으면 **활성화가 취소된다.**
 *
 * dnd-kit 의 DelayConstraint 에서 tolerance 는 선택이 아니라 필수다. 처음 8px 로 뒀는데
 * 그건 손을 그만큼 붙들고 있어야 한다는 뜻이라, 취소된 줄 모르고 다시 누르게 되어
 * 체감 대기시간이 실제 delay 보다 훨씬 길어진다. 손떨림은 흡수하고 의도적인
 * 스크롤·스와이프는 여전히 취소되도록 넉넉하게 잡는다.
 */
export const DRAG_TOLERANCE_PX = 24

/** 드롭 대상 id 를 서비스 표시명으로부터 만든다(미지정 포함). */
export function dropZoneId(serviceName: string): string {
  return `svc:${serviceName}`
}

export function serviceFromDropZoneId(id: string): string | null {
  return id.startsWith('svc:') ? id.slice(4) : null
}
