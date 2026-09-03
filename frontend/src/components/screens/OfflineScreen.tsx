// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useState } from 'react'
import { useKeylens } from '@/store/keylensStore'

/**
 * 백엔드에 연결하지 못했을 때의 화면.
 *
 * 예전에는 이 경우 설정(금고 만들기) 화면을 띄웠는데, 그건 **금고가 있는지조차 모르는
 * 상태에서 "새로 만들기"를 권하는 것**이라 위험했다. 멀쩡히 있는 금고를 잃은 줄 알기 쉽고,
 * 브라우저 자동완성이 비밀번호를 채워두면 버튼만 누르면 되는 것처럼 보인다.
 * 금고는 건드리지 않고 연결 문제만 알린 뒤 다시 시도하게 한다.
 */
export function OfflineScreen() {
  const boot = useKeylens((s) => s.boot)
  const [retrying, setRetrying] = useState(false)

  const retry = async () => {
    setRetrying(true)
    try {
      await boot()
    } finally {
      setRetrying(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-6 text-fg">
      <div className="w-full max-w-[420px] text-center">
        <div className="mx-auto flex size-11 items-center justify-center rounded-full border-[1.5px] border-border-strong bg-surface text-[18px]">
          !
        </div>
        <h1 className="mt-4 text-[17px] font-bold">KeyLens 서버에 연결하지 못했어요</h1>
        <p className="mt-2 text-[13px] leading-[1.7] text-muted">
          금고는 그대로 있습니다. 저장된 자격증명은 이 기기의 암호화된 파일에 남아 있고,
          연결이 되면 그대로 열립니다.
        </p>
        <div className="mt-4 rounded-[8px] border border-line-2 bg-surface-3 px-4 py-3 text-left text-[12px] leading-[1.75] text-faint">
          <div className="mb-1 font-semibold text-fg-soft">확인해 볼 것</div>
          <div>
            개발 모드라면 <code className="font-mono text-fg-soft">node scripts/dev.mjs</code> 가
            떠 있는지, 데스크톱 앱이라면 창이 켜져 있는지 확인해 주세요.
          </div>
        </div>
        <button
          type="button"
          onClick={() => void retry()}
          disabled={retrying}
          className="mt-5 w-full cursor-pointer rounded-lg border-none bg-mint px-4 py-[10px] text-[13px] font-bold text-on-mint hover:brightness-[1.08] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {retrying ? '다시 확인하는 중...' : '다시 시도'}
        </button>
        <p className="mt-3 text-[11.5px] text-faint-2">
          이 화면에서는 금고를 만들거나 지우지 않습니다.
        </p>
      </div>
    </div>
  )
}
