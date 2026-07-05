// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { ReactNode } from 'react'
import { expiryInfo, fmtDate } from '@/lib/format'
import { useKeylens } from '@/store/keylensStore'
import type { VaultItem } from '@/types'

/** 복사 아이콘. */
function CopyIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden="true">
      <rect x="4.5" y="4.5" width="8" height="8" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M9.5 2.5h-6a1 1 0 0 0-1 1v6" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

/** 보관함 항목 한 줄 + 상세 펼침. */
export function VaultRow({ it }: { it: VaultItem }) {
  const locked = useKeylens((s) => s.locked)
  const revealed = useKeylens((s) => s.revealed[it.id])
  const expanded = useKeylens((s) => s.expandedId === it.id)
  const reveal = useKeylens((s) => s.reveal)
  const copyValue = useKeylens((s) => s.copyValue)
  const rotate = useKeylens((s) => s.rotate)
  const toggleExpanded = useKeylens((s) => s.toggleExpanded)
  const setVaultField = useKeylens((s) => s.setVaultField)
  const setDeleteTarget = useKeylens((s) => s.setDeleteTarget)

  const canSee = !locked && !!revealed
  const hasRealImg = !!(it.sourceImage && it.sourceImage !== 'sample')
  const exp = expiryInfo(it.expiresAt)
  const showExp = exp && (exp.expired || exp.days <= 14)
  const urgent = exp && (exp.expired || exp.urgent)
  const expFg = urgent ? '#E5675C' : '#E3B341'
  const copyOp = locked ? 0.35 : 1
  const copyCursor = locked ? 'not-allowed' : 'pointer'

  return (
    <div className="border-t border-[#14181E]">
      <div className="grid grid-cols-[220px_1fr_auto] items-center gap-[14px] px-4 py-[11px] hover:bg-[#13171D]">
        {/* 종류 + 변수명 */}
        <div className="min-w-0">
          <div className="flex items-center gap-[6px] text-[11.5px] text-muted-2">
            {it.project && (
              <span className="max-w-[110px] overflow-hidden text-ellipsis whitespace-nowrap rounded-[4px] border border-[rgba(143,163,191,.22)] bg-[rgba(143,163,191,.1)] px-[6px] py-px text-[10px] font-semibold text-blue-tag">
                {it.project}
              </span>
            )}
            <span className="overflow-hidden text-ellipsis whitespace-nowrap">{it.type}</span>
          </div>
          <div className="mt-[2px] overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[12px] text-fg-soft">
            {it.varName}
          </div>
        </div>

        {/* 값(마스킹/공개 토글) */}
        <div
          onClick={() => reveal(it.id)}
          title={locked ? '잠금 해제 후 볼 수 있어요' : canSee ? '클릭하여 숨기기' : '클릭하여 4초간 표시'}
          className="cursor-pointer overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[12.5px]"
          style={{ color: canSee ? '#A7E8C9' : '#727C89' }}
        >
          {canSee ? it.full : it.masked}
        </div>

        {/* 날짜 · 만료 · 복사 · 삭제 · 펼침 */}
        <div className="flex items-center justify-end gap-[6px]">
          <span className="whitespace-nowrap text-[10.5px] text-dim-2" title={`${fmtDate(it.addedAt, true)} 등록`}>
            {fmtDate(it.addedAt)}
          </span>
          {showExp && exp && (
            <span
              className="whitespace-nowrap rounded-[5px] border px-[7px] py-[2.5px] text-[10.5px] font-bold"
              style={{
                color: expFg,
                background: urgent ? 'rgba(229,103,92,.1)' : 'rgba(227,179,65,.1)',
                borderColor: urgent ? 'rgba(229,103,92,.3)' : 'rgba(227,179,65,.25)',
              }}
            >
              만료 {exp.label}
            </span>
          )}
          <button
            type="button"
            onClick={() => copyValue(it.id, it.varName + ' 복사됨')}
            title="복사"
            className="flex items-center gap-[5px] rounded-[6px] border border-border bg-chip px-[9px] py-[5.5px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
            style={{ opacity: copyOp, cursor: copyCursor }}
          >
            <CopyIcon />
            복사
          </button>
          <button
            type="button"
            onClick={() => setDeleteTarget(it)}
            title="삭제"
            className="cursor-pointer rounded-[6px] border border-transparent bg-none px-2 py-[5px] text-[12px] text-dim-2 hover:border-[rgba(229,103,92,.3)] hover:text-danger"
          >
            ✕
          </button>
          <button
            type="button"
            onClick={() => toggleExpanded(it.id)}
            title="상세 보기"
            className="cursor-pointer rounded-[6px] border border-transparent bg-none px-[7px] py-[5px] text-[11px] text-faint transition-transform hover:text-fg-soft"
            style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
          >
            ▾
          </button>
        </div>
      </div>

      {/* 상세 */}
      {expanded && (
        <div className="flex gap-4 border-t border-[#14181E] bg-[#0D1014] px-4 pb-4 pt-[14px] [animation:klFade_.15s]">
          <div className="w-[150px] flex-none">
            {/* 스크린샷에는 값이 평문으로 찍혀 있다 — 값과 동일한 공개 조건(canSee)으로만 표시. */}
            {hasRealImg && canSee ? (
              <div
                role="img"
                aria-label="원본 스크린샷"
                className="h-[96px] w-[150px] rounded-lg border border-border bg-cover bg-top"
                style={{ backgroundImage: `url(${it.sourceImage})` }}
              />
            ) : (
              <div className="flex h-[96px] w-[150px] items-center justify-center rounded-lg border border-border [background:repeating-linear-gradient(45deg,#12151A,#12151A_6px,#161B21_6px,#161B21_12px)]">
                <span className="px-2 text-center font-mono text-[10px] text-dim">
                  {hasRealImg
                    ? '가려짐 — 값 표시 시 공개'
                    : it.sourceImage === 'sample'
                      ? 'sample screenshot'
                      : '원본 없음'}
                </span>
              </div>
            )}
            <div className="mt-[6px] text-center text-[10.5px] text-dim">원본 스크린샷</div>
          </div>

          <div className="flex min-w-0 flex-1 flex-col gap-[10px]">
            <Row label="등록일">
              <span className="text-fg-soft">{fmtDate(it.addedAt, true)}</span>
            </Row>
            <Row label="프로젝트">
              <input
                value={it.project}
                onChange={(e) => setVaultField(it.id, 'project', e.target.value)}
                list="kl-projects"
                placeholder="프로젝트 없음"
                className="w-[180px] rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[6px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
              />
            </Row>
            {it.context && (
              <Row label="컨텍스트">
                <span className="text-blue-soft">{it.context}</span>
              </Row>
            )}
            <Row label="메모">
              <input
                value={it.memo}
                onChange={(e) => setVaultField(it.id, 'memo', e.target.value)}
                placeholder="언제·왜 발급받은 키인지 메모"
                className="min-w-0 flex-1 rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[6px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
              />
            </Row>
            <Row label="만료일">
              <input
                type="date"
                value={it.expiresAt || ''}
                onChange={(e) => setVaultField(it.id, 'expiresAt', e.target.value || null)}
                className="rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[5px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
              />
              {exp && (
                <span className="text-[11px] font-semibold" style={{ color: expFg }}>
                  {exp.expired ? '만료됨 — 회전하세요' : exp.days + '일 남음'}
                </span>
              )}
            </Row>
            <Row label="이력">
              <span className="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-[11.5px] text-muted-2">
                {(it.history || []).map((h) => h.date + ' ' + h.event).join(' · ') || '기록 없음'}
              </span>
              <button
                type="button"
                onClick={() => rotate(it.id)}
                title="키를 새로 발급받아 교체했다면 회전 기록을 남기세요"
                className="flex-none cursor-pointer rounded-[7px] border border-border bg-chip px-[10px] py-[5px] text-[11px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
              >
                회전 기록
              </button>
            </Row>
            <div className="flex items-start gap-2 text-[12px]">
              <span className="mt-2 w-[52px] flex-none text-dim">비고</span>
              <pre className="m-0 min-w-0 flex-1 whitespace-pre-wrap break-all rounded-[7px] border border-line bg-inset px-[11px] py-[9px] font-mono text-[10.5px] leading-[1.6] text-muted-2">
                {JSON.stringify(it.meta || {}, null, 2)}
              </pre>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => copyValue(it.id, '.env 형식으로 복사됨', it.varName + '=')}
                className="rounded-[7px] border border-border bg-chip px-[11px] py-[6px] font-mono text-[11px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
                style={{ opacity: copyOp, cursor: copyCursor }}
              >
                .env 형식 복사
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-[12px]">
      <span className="w-[52px] flex-none text-dim">{label}</span>
      {children}
    </div>
  )
}
