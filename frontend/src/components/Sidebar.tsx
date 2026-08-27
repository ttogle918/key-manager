// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { cn } from '@/lib/cn'
import { useKeylens } from '@/store/keylensStore'

/** 키홀 로고 마크(민트 원 + 홈). */
function KeyholeMark() {
  return (
    <div className="relative size-[9px] rounded-full bg-[#07231A]">
      <div className="absolute left-1/2 top-[7px] h-[7px] w-[3px] -translate-x-1/2 rounded-[1px] bg-[#07231A]" />
    </div>
  )
}

export function Sidebar() {
  const view = useKeylens((s) => s.view)
  const locked = useKeylens((s) => s.locked)
  const vaultCount = useKeylens((s) => s.vault.length)
  const goInput = useKeylens((s) => s.goInput)
  const goVault = useKeylens((s) => s.goVault)
  const pendingCount = useKeylens((s) => s.pendingRequests.length)
  const goPending = useKeylens((s) => s.goPending)
  const goProjectAccess = useKeylens((s) => s.goProjectAccess)
  const lockNow = useKeylens((s) => s.lockNow)
  const gotoLockScreen = useKeylens((s) => s.gotoLockScreen)
  const openResetVault = useKeylens((s) => s.openResetVault)

  const navBtn = (active: boolean) =>
    cn(
      'flex w-full items-center gap-[9px] rounded-[7px] border-none px-[10px] py-2 text-[13px] font-semibold',
      'cursor-pointer text-left',
      active ? 'bg-[#191F26] text-fg' : 'bg-transparent text-muted',
    )

  return (
    <aside className="sticky top-0 flex h-screen w-[212px] flex-none flex-col border-r border-line bg-sidebar px-3 pb-[14px] pt-[18px]">
      {/* 로고 */}
      <div className="flex items-center gap-[10px] px-2 pb-[18px] pt-1">
        <div className="flex size-7 flex-none items-center justify-center rounded-lg [background:linear-gradient(135deg,#3ECF8E,#28A671)]">
          <KeyholeMark />
        </div>
        <div className="flex-1">
          <div className="text-[14.5px] font-bold tracking-[-.01em]">KeyLens</div>
          <div className="mt-px text-[10.5px] text-faint-2">로컬 자격증명 렌즈</div>
        </div>
        <a
          href="https://ttogle918.github.io/key-manager/onboarding-guide.html"
          target="_blank"
          rel="noopener noreferrer"
          title="시작 가이드 열기"
          className="flex size-[18px] flex-none cursor-pointer items-center justify-center rounded-full border border-border text-[10.5px] font-bold text-faint-2 no-underline hover:border-border-strong hover:text-fg-soft"
        >
          i
        </a>
      </div>

      {/* 내비게이션 */}
      <nav className="flex flex-col gap-[2px]">
        <button type="button" onClick={goInput} className={navBtn(view === 'input')}>
          <span className="block size-[15px] flex-none rounded-[5px] border-[1.5px] border-dashed border-current opacity-70" />
          <span className="flex-1">분석 · 입력</span>
        </button>
        <button type="button" onClick={goVault} className={navBtn(view === 'vault')}>
          <span className="block size-[15px] flex-none rounded-[5px] border-[1.5px] border-current opacity-70" />
          <span className="flex-1">보관함</span>
          <span className="rounded-[10px] bg-[#171C22] px-[7px] py-px text-[11px] font-semibold text-muted-2">
            {vaultCount}
          </span>
        </button>
        <button type="button" onClick={goPending} className={navBtn(view === 'pending')}>
          <span className="block size-[15px] flex-none rounded-full border-[1.5px] border-current opacity-70" />
          <span className="flex-1">승인 대기</span>
          {pendingCount > 0 && (
            <span className="rounded-[10px] bg-[#E3B341] px-[7px] py-px text-[11px] font-semibold text-[#07231A]">
              {pendingCount}
            </span>
          )}
        </button>
        <button type="button" onClick={goProjectAccess} className={navBtn(view === 'projectAccess')}>
          <span className="block size-[15px] flex-none rounded-[3px] border-[1.5px] border-current opacity-70" />
          <span className="flex-1">프로젝트 접근</span>
        </button>
      </nav>

      <div className="flex-1" />

      {/* 잠금 상태 pill */}
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={locked ? gotoLockScreen : lockNow}
          className="flex w-full cursor-pointer items-center gap-2 rounded-lg border border-[#20262E] bg-[#13161B] px-[11px] py-[9px] text-left text-[12.5px] text-fg-soft hover:border-border-strong"
        >
          <span
            className="size-2 flex-none rounded-full"
            style={{
              background: locked ? '#E3B341' : '#3ECF8E',
              boxShadow: `0 0 8px ${locked ? 'rgba(227,179,65,.5)' : 'rgba(62,207,142,.5)'}`,
            }}
          />
          <span className="flex-1 font-semibold">{locked ? '금고 잠김' : '금고 해제됨'}</span>
          <span className="text-[11px] text-faint-2">{locked ? '열기' : '잠그기'}</span>
        </button>
        <button
          type="button"
          onClick={openResetVault}
          title="저장된 모든 자격증명을 완전히 삭제하고 초기 상태로 되돌립니다(되돌릴 수 없음)"
          className="cursor-pointer border-none bg-none px-2 py-[2px] text-left text-[11px] text-dim-3 hover:text-danger"
        >
          금고 완전 초기화
        </button>
      </div>
    </aside>
  )
}
