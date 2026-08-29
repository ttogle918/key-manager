// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect } from 'react'
import { useKeylens } from '@/store/keylensStore'

/** RUNTIME-1 — 컬렉션별 SDK 허용 디렉토리를 미리 등록해 두는 설정 화면.
 * 여기서 등록해 두면 keylens-env가 최초 요청에도 승인 팝업 없이 바로 통과한다. */
export function ProjectAccessScreen() {
  const sdkProjects = useKeylens((s) => s.sdkProjects)
  const selectedSdkProject = useKeylens((s) => s.selectedSdkProject)
  const sdkDirs = useKeylens((s) => s.sdkDirs)
  const newDirPath = useKeylens((s) => s.newDirPath)
  const loadSdkProjects = useKeylens((s) => s.loadSdkProjects)
  const selectSdkProject = useKeylens((s) => s.selectSdkProject)
  const setNewDirPath = useKeylens((s) => s.setNewDirPath)
  const addSdkDir = useKeylens((s) => s.addSdkDir)
  const removeSdkDir = useKeylens((s) => s.removeSdkDir)

  useEffect(() => {
    loadSdkProjects()
  }, [loadSdkProjects])

  return (
    <div className="mx-auto max-w-[720px] px-8 pb-[90px] pt-[44px] [animation:klFadeUp_.35s_ease]">
      <div className="mb-[18px]">
        <h1 className="m-0 text-[20px] font-bold tracking-[-.015em]">컬렉션 접근</h1>
        <div className="mt-1 text-[12.5px] text-faint-2">
          keylens-env SDK가 승인 팝업 없이 바로 통과할 디렉토리를 컬렉션별로 미리 등록해 두세요.
        </div>
      </div>

      {sdkProjects.length === 0 ? (
        <div className="rounded-xl border border-border bg-panel px-5 py-8 text-center text-[13px] text-muted">
          컬렉션이 지정된 키가 아직 없어요 — 보관함에서 항목에 컬렉션을 먼저 지정하세요.
        </div>
      ) : (
        <div className="flex gap-4">
          <div className="flex w-[220px] flex-none flex-col gap-1">
            {sdkProjects.map((p) => (
              <button
                key={p.project}
                type="button"
                onClick={() => selectSdkProject(p.project)}
                className={
                  'flex items-center justify-between rounded-lg border px-3 py-[9px] text-left text-[12.5px] font-semibold ' +
                  (p.project === selectedSdkProject
                    ? 'border-[rgba(62,207,142,.55)] bg-[#191F26] text-fg'
                    : 'border-border bg-surface text-muted hover:border-border-strong')
                }
              >
                <span className="truncate">{p.project}</span>
                <span className="text-[11px] text-faint-2">{p.keyCount}</span>
              </button>
            ))}
          </div>

          <div className="min-w-0 flex-1">
            {!selectedSdkProject ? (
              <div className="rounded-xl border border-border bg-panel px-5 py-8 text-center text-[13px] text-muted">
                왼쪽에서 컬렉션을 선택하세요.
              </div>
            ) : (
              <>
                <div className="mb-3 flex gap-2">
                  <input
                    value={newDirPath}
                    onChange={(e) => setNewDirPath(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') addSdkDir()
                    }}
                    placeholder="예: C:\repo\블로그 또는 /home/user/repo/blog"
                    className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-[9px] font-mono text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
                  />
                  <button
                    type="button"
                    onClick={addSdkDir}
                    className="cursor-pointer rounded-lg border-none bg-mint px-4 py-[9px] text-[12.5px] font-bold text-on-mint hover:brightness-[1.07]"
                  >
                    등록
                  </button>
                </div>

                {sdkDirs.length === 0 ? (
                  <div className="rounded-xl border border-border bg-panel px-5 py-8 text-center text-[13px] text-muted">
                    등록된 디렉토리가 없어요.
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    {sdkDirs.map((d) => (
                      <div
                        key={d.id}
                        className="flex items-center gap-3 rounded-xl border border-border bg-panel px-4 py-[12px]"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-mono text-[12.5px] text-fg-soft">{d.path}</div>
                          <div className="mt-[3px] text-[10.5px] text-dim-3">
                            {d.source === 'manual' ? '사전 등록' : '승인으로 등록됨'} · {d.createdAt}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeSdkDir(d.id)}
                          className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
                        >
                          해제
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
