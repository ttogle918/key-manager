// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect } from 'react'
import { useKeylens } from '@/store/keylensStore'

/** RUNTIME-1 — SDK 승인 대기 화면. 미등록 디렉토리의 keylens-env 요청을 확인해 허용/거부한다. */
export function PendingScreen() {
  const pendingRequests = useKeylens((s) => s.pendingRequests)
  const loadPending = useKeylens((s) => s.loadPending)
  const approvePending = useKeylens((s) => s.approvePending)
  const denyPending = useKeylens((s) => s.denyPending)

  // mount 시에도 직접 조회 — 수동 진입·다건 대기 케이스 커버(데스크톱 알림 없이도 확인 가능).
  useEffect(() => {
    loadPending()
  }, [loadPending])

  return (
    <div className="mx-auto max-w-[640px] px-8 pb-[90px] pt-[44px] [animation:klFadeUp_.35s_ease]">
      <div className="mb-[18px]">
        <h1 className="m-0 text-[20px] font-bold tracking-[-.015em]">승인 대기</h1>
        <div className="mt-1 text-[12.5px] text-faint-2">
          keylens-env SDK가 미등록 디렉토리에서 컬렉션의 키를 요청했어요 — 허용해야 값을 내려줍니다.
        </div>
      </div>

      {pendingRequests.length === 0 ? (
        <div className="rounded-xl border border-border bg-panel px-5 py-8 text-center text-[13px] text-muted">
          대기 중인 요청이 없어요.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {pendingRequests.map((r) => (
            <div
              key={r.id}
              className="flex items-center gap-3 rounded-xl border border-border bg-panel px-4 py-[14px]"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13.5px] font-semibold text-fg-soft">{r.project}</div>
                <div className="mt-[3px] truncate font-mono text-[11.5px] text-muted">{r.path}</div>
                <div className="mt-[3px] text-[10.5px] text-dim-3">{r.requestedAt}</div>
              </div>
              <button
                type="button"
                onClick={() => denyPending(r.id)}
                className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
              >
                거부
              </button>
              <button
                type="button"
                onClick={() => approvePending(r.id)}
                className="cursor-pointer rounded-lg border-none bg-mint px-3 py-[9px] text-[12.5px] font-bold text-on-mint hover:brightness-[1.07]"
              >
                허용
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
