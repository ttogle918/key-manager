// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useKeylens } from '@/store/keylensStore'

/** 하단 중앙 토스트. */
export function Toast() {
  const toast = useKeylens((s) => s.toast)
  if (!toast) return null
  return (
    <div
      role="status"
      className="fixed bottom-[26px] left-1/2 z-[90] flex -translate-x-1/2 items-center gap-[9px] whitespace-nowrap rounded-[9px] border border-[#2A323D] bg-[#1B222B] px-[15px] py-[9px] text-[12.5px] text-[#DEE3EA] shadow-[0_10px_30px_rgba(0,0,0,.45)] [animation:klFadeUp_.2s_ease]"
    >
      <span className="size-[7px] flex-none rounded-full bg-mint" />
      {toast}
    </div>
  )
}
