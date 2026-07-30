// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { KeyboardEvent } from 'react'
import { strengthLevel } from '@/lib/format'
import { useKeylens } from '@/store/keylensStore'

const LVL_COLORS = ['#20262E', '#E5675C', '#E3B341', '#8FD46A', '#3ECF8E']
const LVL_LABELS = ['', '약함', '보통', '좋음', '강함']

/** 화면 3a: 최초 실행 — 마스터 비밀번호 설정. */
export function SetupScreen() {
  const pw = useKeylens((s) => s.pw)
  const pw2 = useKeylens((s) => s.pw2)
  const setupErr = useKeylens((s) => s.setupErr)
  const unlocking = useKeylens((s) => s.unlocking)
  const setPw = useKeylens((s) => s.setPw)
  const setPw2 = useKeylens((s) => s.setPw2)
  const createVault = useKeylens((s) => s.createVault)

  const lvl = strengthLevel(pw)
  const createOk = pw.length > 0 && pw2.length > 0
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter') createVault()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg">
      <div
        className="w-[340px] text-center"
        style={{
          animation: unlocking
            ? 'klVaultOut .55s ease forwards'
            : 'klFadeUp .35s ease',
        }}
      >
        <div className="mx-auto flex size-16 items-center justify-center rounded-full border-[1.5px] border-border bg-panel">
          <div className="flex size-10 items-center justify-center rounded-full border-[1.5px] border-border-strong">
            <div className="relative size-[10px] rounded-full border-2 border-mint">
              <div className="absolute left-1/2 top-[9px] h-2 w-[3px] -translate-x-1/2 rounded-[1px] bg-mint" />
            </div>
          </div>
        </div>
        <div className="mt-5 text-[17px] font-bold tracking-[-.01em]">마스터 비밀번호 설정</div>
        <div className="mt-[6px] text-[12.5px] leading-[1.5] text-muted">
          값은 마스터 비밀번호에서 Argon2id로 유도한 키로 AES-256-GCM 암호화되어
          <br />
          이 기기에만 저장됩니다. 비밀번호·키는 디스크에 남지 않습니다.
          <br />
          영문·숫자·특수문자를 모두 섞으면 8자 이상, 2종류만 섞으면 10자 이상이어야 해요.
        </div>

        <input
          type="password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          onKeyDown={onKey}
          placeholder="마스터 비밀번호 (영문·숫자·특수문자 조합)"
          className="mt-[22px] w-full rounded-[9px] border border-border bg-surface px-[13px] py-[11px] text-[13.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
        />

        <div className="mt-[10px] flex items-center gap-2">
          <div className="flex flex-1 gap-1">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-1 flex-1 rounded-[2px] transition-colors"
                style={{ background: i <= lvl ? LVL_COLORS[lvl] : '#20262E' }}
              />
            ))}
          </div>
          <span
            className="w-[34px] text-right text-[11px] font-bold"
            style={{ color: LVL_COLORS[lvl] || '#525B67' }}
          >
            {LVL_LABELS[lvl]}
          </span>
        </div>

        <input
          type="password"
          value={pw2}
          onChange={(e) => setPw2(e.target.value)}
          onKeyDown={onKey}
          placeholder="비밀번호 확인"
          className="mt-[10px] w-full rounded-[9px] border border-border bg-surface px-[13px] py-[11px] text-[13.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
        />

        {setupErr && <div className="mt-[10px] text-left text-[12px] text-danger">{setupErr}</div>}

        <div className="mt-[14px] flex gap-2 rounded-[9px] border border-[rgba(227,179,65,.28)] bg-[rgba(227,179,65,.05)] px-3 py-[10px] text-left text-[11.5px] leading-[1.55] text-amber-soft">
          <span className="mt-1 inline-block size-[7px] flex-none rotate-45 bg-amber" />
          <span>
            비밀번호는 어디에도 저장·전송되지 않습니다.{' '}
            <strong className="font-bold">분실하면 저장된 모든 자격증명을 복구할 수 없습니다.</strong>
          </span>
        </div>

        <button
          type="button"
          onClick={createVault}
          disabled={!createOk}
          className="mt-4 w-full rounded-[9px] border-none py-3 text-[13.5px] font-bold hover:brightness-[1.07] disabled:cursor-not-allowed"
          style={{
            background: createOk ? '#3ECF8E' : '#1B2128',
            color: createOk ? '#05231A' : '#525B67',
            cursor: createOk ? 'pointer' : 'not-allowed',
          }}
        >
          금고 만들기
        </button>
        <div className="mt-4 text-[11px] text-dim-3">외부 서버 없음 · 로컬 우선(local-first)</div>
      </div>
    </div>
  )
}
