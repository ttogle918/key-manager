// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect, useState } from 'react'
import { useKeylens } from '@/store/keylensStore'

/** RUNTIME-1 — SDK 승인 대기 화면. 미등록 디렉토리의 keylens-env 요청을 확인해 허용/거부한다. */
export function PendingScreen() {
  const pendingRequests = useKeylens((s) => s.pendingRequests)
  const loadPending = useKeylens((s) => s.loadPending)
  const approvePending = useKeylens((s) => s.approvePending)
  const denyPending = useKeylens((s) => s.denyPending)
  const allSdkDirs = useKeylens((s) => s.allSdkDirs)
  const loadAllSdkDirs = useKeylens((s) => s.loadAllSdkDirs)
  const revokeSdkDir = useKeylens((s) => s.revokeSdkDir)

  /**
   * 이미 허용한 목록은 기본으로 접어 둔다. 이 화면의 본래 일은 "지금 결정할 것"을 보여주는
   * 것이고, 허용 이력은 가끔 확인·정리하는 참고 자료다.
   */
  const [allowedOpen, setAllowedOpen] = useState(false)

  // mount 시에도 직접 조회 — 수동 진입·다건 대기 케이스 커버(데스크톱 알림 없이도 확인 가능).
  useEffect(() => {
    loadPending()
    // 접혀 있어도 미리 불러둔다 - 개수를 요약에 보여줘야 펼칠지 말지 판단할 수 있다.
    loadAllSdkDirs()
  }, [loadPending, loadAllSdkDirs])

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

      <section className="mt-6">
        <button
          type="button"
          onClick={() => setAllowedOpen((v) => !v)}
          aria-expanded={allowedOpen}
          className="flex w-full cursor-pointer items-center gap-2 rounded-xl border border-border bg-panel px-4 py-[12px] text-left hover:border-border-strong"
        >
          <span
            aria-hidden
            className={`text-[11px] text-dim-3 transition-transform ${allowedOpen ? 'rotate-90' : ''}`}
          >
            &#9654;
          </span>
          <span className="flex-1 text-[13px] font-semibold text-fg-soft">이미 허용한 디렉토리</span>
          <span className="text-[11.5px] text-dim-3">{allSdkDirs.length}개</span>
        </button>

        {allowedOpen && (
          <div className="mt-2 flex flex-col gap-2">
            {allSdkDirs.length === 0 ? (
              <div className="rounded-xl border border-border bg-panel px-5 py-6 text-center text-[12.5px] text-muted">
                허용된 디렉토리가 없어요.
              </div>
            ) : (
              allSdkDirs.map((d) => (
                <div
                  key={`${d.project}:${d.id}`}
                  className="flex items-center gap-3 rounded-xl border border-border bg-panel px-4 py-[12px]"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12.5px] font-semibold text-fg-soft">{d.project}</div>
                    <div className="mt-[3px] truncate font-mono text-[11.5px] text-muted">{d.path}</div>
                    <div className="mt-[3px] text-[10.5px] text-dim-3">
                      {d.source === 'manual' ? '사전 등록' : '승인으로 등록됨'} · {d.createdAt}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => revokeSdkDir(d.project, d.id)}
                    title="이 디렉토리의 접근을 막습니다 - 다음 요청부터 다시 승인을 받습니다"
                    className="shrink-0 cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
                  >
                    철회
                  </button>
                </div>
              ))
            )}
          </div>
        )}
      </section>
    </div>
  )
}
