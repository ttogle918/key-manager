// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { KeyboardEvent } from 'react'
import { useKeylens } from '@/store/keylensStore'

/** 화면 3b: 잠금 / 인증. */
export function LockScreen() {
  const lockPw = useKeylens((s) => s.lockPw)
  const lockErr = useKeylens((s) => s.lockErr)
  const lockShakeN = useKeylens((s) => s.lockShakeN)
  const unlocking = useKeylens((s) => s.unlocking)
  const setLockPw = useKeylens((s) => s.setLockPw)
  const submitUnlock = useKeylens((s) => s.submitUnlock)
  const openForgotReset = useKeylens((s) => s.openForgotReset)

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter') submitUnlock()
  }
  const shakeName = lockShakeN % 2 ? 'klShake' : 'klShake'
  const keyholeColor = unlocking ? '#3ECF8E' : '#8B93A1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg">
      <div
        className="w-[300px] text-center"
        style={{ animation: unlocking ? 'klVaultOut .6s ease .2s forwards' : 'klFadeUp .35s ease' }}
      >
        <div
          className="relative mx-auto flex size-[72px] items-center justify-center rounded-full border-[1.5px] bg-panel transition-colors"
          style={{
            borderColor: unlocking ? 'rgba(62,207,142,.6)' : '#232931',
            animation: unlocking ? 'klRingSpin .55s ease' : 'none',
          }}
        >
          <div className="absolute left-1/2 top-[5px] h-[7px] w-[3px] -translate-x-1/2 rounded-[2px] bg-border-strong" />
          <div className="flex size-[46px] items-center justify-center rounded-full border-[1.5px] border-border-strong">
            <div
              className="relative size-[11px] rounded-full border-2 transition-colors"
              style={{ borderColor: keyholeColor }}
            >
              <div
                className="absolute left-1/2 top-[10px] h-2 w-[3px] -translate-x-1/2 rounded-[1px] transition-colors"
                style={{ background: keyholeColor }}
              />
            </div>
          </div>
        </div>

        <div className="mt-5 text-[17px] font-bold tracking-[-.01em]">KeyLens 잠김</div>
        <div className="mt-[5px] text-[12.5px] text-muted">마스터 비밀번호로 금고를 여세요</div>

        <div style={{ animation: lockErr ? `${shakeName} .4s ease` : 'none' }}>
          <input
            type="password"
            value={lockPw}
            onChange={(e) => setLockPw(e.target.value)}
            onKeyDown={onKey}
            autoFocus
            placeholder="마스터 비밀번호"
            className="mt-[22px] w-full rounded-[9px] border bg-surface px-[13px] py-[11px] text-center text-[14px] tracking-[.15em] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
            style={{ borderColor: lockErr ? 'rgba(229,103,92,.55)' : '#232931' }}
          />
        </div>

        {lockErr && <div className="mt-[9px] text-[12px] text-danger">{lockErr}</div>}

        <button
          type="button"
          onClick={submitUnlock}
          className="mt-[14px] w-full cursor-pointer rounded-[9px] border-none bg-mint py-3 text-[13.5px] font-bold text-on-mint hover:brightness-[1.07]"
        >
          {unlocking ? '여는 중…' : '잠금 해제'}
        </button>
        {/* 비밀번호를 잊으면 앱 안에 나갈 길이 있어야 한다. 없으면 사용자는 vault.db 를
            직접 찾아 지워야 한다는 걸 스스로 알아내야 하고, 대부분은 못 한다. */}
        <button
          type="button"
          onClick={openForgotReset}
          className="mt-[14px] cursor-pointer border-none bg-none text-[11.5px] text-dim-3 underline underline-offset-2 hover:text-muted"
        >
          비밀번호를 잊으셨나요?
        </button>
        <div className="mt-3 text-[11px] text-dim-3">서버 전송 없음 · 마스터 비밀번호로 로컬 인증(틀리면 복호화 거부)</div>
      </div>
    </div>
  )
}
