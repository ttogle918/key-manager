// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { CONF_META, SVC_META, TYPE_MAP } from '@/data/services'
import { KeyHelp } from '@/components/KeyHelp'
import { useKeylens } from '@/store/keylensStore'
import type { AnalysisResult } from '@/types'

/** 분석 결과 카드 한 장. 신뢰도·신호 충돌 해소·변수명 매핑·저장을 담는다. */
export function ResultCard({ r }: { r: AnalysisResult }) {
  const patchResult = useKeylens((s) => s.patchResult)
  const pickOption = useKeylens((s) => s.pickOption)
  const setType = useKeylens((s) => s.setType)
  const save = useKeylens((s) => s.save)

  const tmap = TYPE_MAP[r.service]
  const cur = tmap.find((t) => t.v === r.typeKey) || null
  const confKey = r.conflict ? (cur ? 'manual' : 'low') : r.conf
  const cm = CONF_META[confKey]
  const svc = SVC_META[r.service]
  const unresolved = !!r.conflict && !cur

  // OCR 이 이어붙인 이음매 위에 빨간 'v' 표식(사용자 확인용). 값·표식은 모노스페이스로 열 정렬.
  const marks = new Set(r.ocrUncertain ?? [])
  const caretRow = marks.size
    ? Array.from(r.full, (_, i) => (marks.has(i) ? 'v' : ' ')).join('')
    : ''
  const typeOpts = (unresolved ? [{ v: '', label: '종류 선택…' }] : []).concat(
    tmap.map((t) => ({ v: t.v, label: t.label })),
  )

  return (
    <div
      className="mb-3 rounded-[11px] border bg-surface [animation:klFadeUp_.3s_ease]"
      style={{
        borderColor: unresolved ? 'rgba(227,179,65,.4)' : '#20262E',
        boxShadow: unresolved
          ? '0 0 0 3px rgba(227,179,65,.06), 0 8px 24px rgba(0,0,0,.25)'
          : 'none',
      }}
    >
      {/* 헤더: 타일 + 서비스/종류 + 신뢰도 뱃지 */}
      <div className="flex items-center gap-[11px] px-4 pt-[14px]">
        <div
          className="flex size-[30px] flex-none items-center justify-center rounded-[7px] text-[14px] font-extrabold"
          style={{ background: svc.bg, color: svc.fg }}
        >
          {svc.tile}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[13.5px] font-semibold">
            {r.service} <span className="font-normal text-faint">/ {cur ? cur.label : '종류 미확정'}</span>
          </div>
          <div className="mt-px text-[11.5px] text-dim">{r.source}</div>
        </div>
        <span
          className="whitespace-nowrap rounded-[6px] border px-2 py-[3px] text-[11px] font-bold"
          style={{ background: cm.bg, color: cm.fg, borderColor: cm.border }}
        >
          {cm.label}
        </span>
      </div>

      {/* 마스킹된 값 + 포맷 */}
      <div className="mx-4 mt-3 flex items-center justify-between gap-3 rounded-lg border border-line bg-inset px-3 py-[10px]">
        <span className="overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[13px] text-fg-soft">
          {r.masked}
        </span>
        <span className="flex-none font-mono text-[10.5px] text-dim-2">{r.format}</span>
      </div>

      {/* 값 절단 경고 — NAME=VALUE 에서 값이 #·따옴표에서 잘렸을 수 있음(Stage1) */}
      {r.meta?.truncated === true && (
        <div className="mx-4 mt-[6px] flex items-start gap-[7px] rounded-lg border border-[rgba(227,179,65,.28)] bg-[rgba(227,179,65,.05)] px-3 py-2 text-[11.5px] leading-[1.5] text-amber">
          <span className="relative top-[3px] inline-block size-[7px] flex-none rotate-45 bg-amber" />
          <span>
            값이 <span className="font-mono">#</span> 또는 따옴표에서 잘렸을 수 있어요 — 원본 전체가 맞는지 확인 후 저장하세요.
          </span>
        </div>
      )}

      {/* OCR 이어붙임 확인 — 이음매 위 빨간 v 표식 + 원본 복사 권장 */}
      {caretRow && (
        <div className="mx-4 mt-[6px] rounded-lg border border-[rgba(227,179,65,.28)] bg-[rgba(227,179,65,.05)] px-3 py-2">
          <div className="mb-[5px] flex items-center gap-[7px] text-[11.5px] font-semibold text-amber">
            <span className="inline-block size-[7px] flex-none rotate-45 bg-amber" />
            OCR가 여기를 이어붙였어요 — 원본을 복사해 확인하세요
          </div>
          <div className="overflow-x-auto">
            <pre className="m-0 font-mono text-[12.5px] leading-[1.25]">
              <span className="text-[#ff5a5a]">{caretRow}</span>
              {'\n'}
              <span className="text-fg-soft">{r.full}</span>
            </pre>
          </div>
        </div>
      )}

      {/* 컨텍스트 노트 */}
      {r.context && (
        <div className="mx-4 mt-[10px] flex items-baseline gap-[7px] text-[12px] text-blue-soft">
          <span className="relative -top-px size-[6px] flex-none rounded-full bg-blue" />
          {r.context}
        </div>
      )}
      {r.midNote && (
        <div className="mx-4 mt-[10px] flex items-baseline gap-[7px] text-[12px] text-muted-2">
          <span className="relative -top-px size-[6px] flex-none rounded-full bg-[#8FA3BF]" />
          {r.midNote}
        </div>
      )}
      {r.dupNote && (
        <div className="mx-4 mt-[10px] flex items-baseline gap-[7px] text-[12px] text-amber">
          <span className="relative -top-px inline-block size-[7px] flex-none rotate-45 bg-amber" />
          {r.dupNote}
        </div>
      )}

      {/* 키 발급 도움말(GUIDE-1) — 종류가 정해졌을 때만 */}
      {cur && (
        <div className="mx-4 mt-[10px]">
          <KeyHelp
            service={r.service}
            typeKey={r.typeKey}
            project={(r.meta?.['gcp_project'] as string) || r.project}
          />
        </div>
      )}

      {/* 신호 충돌 — 종류 직접 선택 */}
      {r.conflict && (
        <div className="mx-4 mt-3 rounded-[9px] border border-[rgba(227,179,65,.28)] bg-[rgba(227,179,65,.05)] px-[13px] py-3">
          <div className="flex items-center gap-2 text-[12.5px] font-bold text-amber">
            <span className="inline-block size-[7px] flex-none rotate-45 bg-amber" />
            신호 충돌 — 같은 UUID 형식이 두 가지로 해석됩니다
          </div>
          <div className="mb-[2px] mt-[5px] text-[12px] leading-[1.5] text-muted">
            맥락 신호를 확인하고 종류를 직접 선택해 주세요.
          </div>
          {(r.options || []).map((o) => {
            const sel = r.typeKey === o.k
            return (
              <button
                type="button"
                key={o.k}
                onClick={() => pickOption(r.id, o.k)}
                className="mt-2 flex w-full cursor-pointer items-start gap-[10px] rounded-lg border px-3 py-[10px] text-left transition-colors hover:border-[rgba(62,207,142,.45)]"
                style={{
                  borderColor: sel ? 'rgba(62,207,142,.55)' : '#262D36',
                  background: sel ? 'rgba(62,207,142,.07)' : '#12151A',
                }}
              >
                <span
                  className="mt-[2px] size-[14px] flex-none rounded-full border-[1.5px]"
                  style={{
                    borderColor: sel ? '#3ECF8E' : '#39424E',
                    background: sel ? '#3ECF8E' : 'transparent',
                    boxShadow: sel ? 'inset 0 0 0 3px #12151A' : 'none',
                  }}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-2 text-[13px] font-semibold">
                    {o.label}
                    <span className="font-mono text-[11px] font-normal text-faint">{o.varName}</span>
                  </div>
                  <div className="mt-[3px] text-[12px] leading-[1.45] text-muted">{o.evidence}</div>
                </div>
                <span
                  className="mt-[2px] flex-none text-[10.5px] font-bold"
                  style={{ color: o.strong ? '#5FD9A4' : '#727C89' }}
                >
                  {o.signal}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {/* 프로젝트 · 메모 · 추출정보 토글 */}
      <div className="mx-4 mt-3 flex items-center gap-2">
        <input
          value={r.project}
          onChange={(e) => patchResult(r.id, { project: e.target.value, dupNote: null })}
          list="kl-projects"
          placeholder="프로젝트"
          className="w-[150px] flex-none rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[7px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
        />
        <input
          value={r.memo}
          onChange={(e) => patchResult(r.id, { memo: e.target.value })}
          placeholder="언제·왜 발급받은 키인지 (선택)"
          className="min-w-0 flex-1 rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[7px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
        />
        <button
          type="button"
          onClick={() => patchResult(r.id, { metaOpen: !r.metaOpen })}
          className="flex-none cursor-pointer rounded-[7px] border border-border bg-none px-[10px] py-[7px] font-mono text-[11px] font-semibold text-faint hover:border-border-strong hover:text-fg-soft"
        >
          {'{ }'} 추출 정보
        </button>
      </div>
      {r.metaOpen && (
        <pre className="mx-4 mt-[10px] whitespace-pre-wrap break-all rounded-lg border border-line bg-inset px-[13px] py-[11px] font-mono text-[11px] leading-[1.6] text-muted-2">
          {JSON.stringify(r.meta || {}, null, 2)}
        </pre>
      )}

      {/* 하단: 변수명 + 종류 선택 + 저장 */}
      <div className="flex items-center gap-[10px] px-4 pb-[14px] pt-3">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className="flex-none text-[11.5px] text-dim">환경변수</span>
          <span
            className="overflow-hidden text-ellipsis whitespace-nowrap rounded-[6px] px-2 py-1 font-mono text-[12px] font-semibold"
            style={{
              background: cur ? 'rgba(62,207,142,.08)' : 'rgba(227,179,65,.08)',
              color: cur ? '#A7E8C9' : '#8B7B4A',
            }}
          >
            {cur ? cur.var : '종류 선택 대기'}
          </span>
        </div>
        <select
          value={r.typeKey || ''}
          onChange={(e) => setType(r.id, e.target.value)}
          className="cursor-pointer rounded-[7px] border border-border-input bg-chip px-[9px] py-[7px] text-[12.5px] text-fg-soft outline-none"
        >
          {typeOpts.map((t) => (
            <option key={t.v} value={t.v}>
              {t.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => save(r.id)}
          disabled={!cur}
          className="rounded-lg border-none px-[14px] py-2 text-[12.5px] font-bold hover:brightness-[1.07]"
          style={{
            background: cur ? '#3ECF8E' : '#1B2128',
            color: cur ? '#05231A' : '#525B67',
            cursor: cur ? 'pointer' : 'not-allowed',
          }}
        >
          확정 후 저장
        </button>
      </div>
    </div>
  )
}
