// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useMemo } from 'react'
import { ExposureBadge } from '@/components/KeyHelp'
import { findServiceByVarName, TYPE_MAP } from '@/data/services'
import { useKeylens } from '@/store/keylensStore'
import { AutocompleteNameInput } from './AutocompleteNameInput'

/**
 * 화면 1의 "직접 입력" 탭 — 맥락 추론(OCR·Stage2) 없이 이미 알고 있는 이름=값을 바로 등록한다.
 * 환경변수명이 지식베이스와 정확히 일치하면 서비스·노출등급을 참고로 보여주지만, 최종 이름은
 * 항상 사용자가 입력한 그대로 저장된다.
 */
export function ManualEntryTab() {
  const rows = useKeylens((s) => s.manualRows)
  const vault = useKeylens((s) => s.vault)
  const knowledgeReady = useKeylens((s) => s.knowledgeReady)
  const projVal = useKeylens((s) => s.projVal)
  const memoVal = useKeylens((s) => s.memoVal)
  const setProj = useKeylens((s) => s.setProj)
  const setMemo = useKeylens((s) => s.setMemo)
  const setManualField = useKeylens((s) => s.setManualField)
  const splitManualField = useKeylens((s) => s.splitManualField)
  const addManualRow = useKeylens((s) => s.addManualRow)
  const removeManualRow = useKeylens((s) => s.removeManualRow)
  const saveManualRows = useKeylens((s) => s.saveManualRows)

  // knowledgeReady 는 /knowledge 로딩 완료 시 값이 바뀌어 이 목록을 다시 계산하게 만드는
  // 트리거용 — TYPE_MAP 자체는 모듈 바인딩이라 매번 최신값을 읽는다.
  const candidates = useMemo(() => {
    const kbNames = Object.values(TYPE_MAP).flatMap((types) => types.map((t) => t.var))
    const vaultNames = vault.map((v) => v.varName)
    return [...kbNames, ...vaultNames]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [knowledgeReady, vault])

  const savableCount = rows.filter((r) => r.name.trim() && r.value.trim()).length

  return (
    <div className="overflow-hidden rounded-[14px] border border-line-2 bg-surface-2">
      <p className="px-[14px] pt-[14px] text-[12px] leading-[1.55] text-muted">
        이미 뭔지 아는 키는 맥락 분류 없이 바로 등록하세요. 예:{' '}
        <code className="font-mono text-fg-soft">OPENAI_API_KEY=sk-…</code> 형태로 붙여넣고{' '}
        <kbd className="rounded border border-border px-1 text-[10.5px]">Enter</kbd>를 누르면 이름·값
        두 칸으로 나뉩니다. 이름 칸에서 <kbd className="rounded border border-border px-1 text-[10.5px]">Tab</kbd>
        을 누르면 알려진 이름으로 자동완성됩니다(다시 누르면 다음 후보).
      </p>

      <div className="flex flex-col gap-[10px] px-[14px] py-[14px]">
        {rows.map((row) => {
          const found = row.name.trim() ? findServiceByVarName(row.name.trim()) : null
          return (
            <div key={row.id} className="flex flex-col gap-[6px]">
              <div className="flex items-center gap-[8px]">
                <div className="w-[240px] flex-none">
                  <AutocompleteNameInput
                    value={row.name}
                    onChange={(v) => setManualField(row.id, 'name', v)}
                    onEnter={() => splitManualField(row.id, 'name')}
                    candidates={candidates}
                    placeholder="OPENAI_API_KEY"
                  />
                </div>
                <input
                  value={row.value}
                  onChange={(e) => setManualField(row.id, 'value', e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') splitManualField(row.id, 'value')
                  }}
                  placeholder="값(value)"
                  className="min-w-0 flex-1 rounded-lg border border-border bg-surface px-3 py-[10px] font-mono text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
                />
                <button
                  type="button"
                  onClick={() => removeManualRow(row.id)}
                  disabled={rows.length <= 1}
                  className="flex-none cursor-pointer rounded-[6px] border border-border bg-none px-[9px] py-[8px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft disabled:cursor-not-allowed disabled:opacity-40"
                >
                  삭제
                </button>
              </div>
              {found && (
                <div className="ml-[248px] flex items-center gap-[8px] text-[11px] text-faint-2">
                  <span>
                    {found.service} · {found.type.label}로 인식됨
                  </span>
                  <ExposureBadge exposure={found.type.exposure} />
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="flex gap-3 px-[14px] pb-[14px]">
        <div className="w-[200px] flex-none">
          <div className="mb-[6px] text-[11.5px] font-semibold text-muted-2">
            컬렉션 <span className="font-medium text-dim-2">(선택)</span>
          </div>
          <input
            value={projVal}
            onChange={(e) => setProj(e.target.value)}
            list="kl-projects"
            placeholder="예: 개인 블로그"
            className="w-full rounded-lg border border-border bg-surface px-3 py-[10px] text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-[6px] text-[11.5px] font-semibold text-muted-2">
            메모 <span className="font-medium text-dim-2">(언제·왜 발급받은 키인가요?)</span>
          </div>
          <input
            value={memoVal}
            onChange={(e) => setMemo(e.target.value)}
            placeholder="예: 6월 사이드프로젝트 블로그 자동화용으로 발급"
            className="w-full rounded-lg border border-border bg-surface px-3 py-[10px] text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
          />
        </div>
      </div>

      <div className="flex items-center gap-3 border-t border-line-2 p-[14px]">
        <button
          type="button"
          onClick={addManualRow}
          className="flex-none cursor-pointer rounded-[9px] border border-border bg-none px-[14px] py-[9px] text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          + 행 추가
        </button>
        <div className="flex-1" />
        <button
          type="button"
          onClick={saveManualRows}
          disabled={!savableCount}
          className="flex-none cursor-pointer rounded-[9px] border-none bg-mint px-[22px] py-[11px] text-[13.5px] font-bold text-on-mint hover:brightness-[1.08] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {savableCount}개 저장
        </button>
      </div>
    </div>
  )
}
