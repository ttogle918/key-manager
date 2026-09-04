// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect } from 'react'

declare global {
  interface Window {
    /** 데스크톱 알림(desktop/notify.py)이 evaluate_js로 호출하는 진입점 — 즉시 승인 대기 화면 전환. */
    __keylensGoPending?: () => void
  }
}
import { useKeylens } from '@/store/keylensStore'
import { Sidebar } from '@/components/Sidebar'
import { OfflineScreen } from '@/components/screens/OfflineScreen'
import { SetupScreen } from '@/components/screens/SetupScreen'
import { LockScreen } from '@/components/screens/LockScreen'
import { InputScreen } from '@/components/screens/InputScreen'
import { VaultScreen } from '@/components/screens/VaultScreen'
import { PendingScreen } from '@/components/screens/PendingScreen'
import { ProjectAccessScreen } from '@/components/screens/ProjectAccessScreen'
import { DeleteModal, DupModal, EmailSyncModal, EnvModal, ForgotResetModal, ResetVaultModal, RotateModal, SyncModal } from '@/components/modals/Modals'
import { ExplainModal } from '@/components/modals/ExplainModal'
import { EnvImportModal } from '@/components/modals/EnvImportModal'
import { Toast } from '@/components/ui/Toast'
import { ProjectsDatalist } from '@/components/ProjectsDatalist'

export default function App() {
  const screen = useKeylens((s) => s.screen)
  const view = useKeylens((s) => s.view)

  // 앱 시작 시 백엔드 금고 상태로 화면(설정/잠금/앱) 결정.
  useEffect(() => {
    useKeylens.getState().boot()
  }, [])

  // 데스크톱 알림이 evaluate_js로 호출할 진입점 등록(RUNTIME-1).
  useEffect(() => {
    window.__keylensGoPending = () => useKeylens.getState().goPending()
    return () => {
      delete window.__keylensGoPending
    }
  }, [])

  // 전역 붙여넣기: 입력 화면에서 **이미지(스크린샷)만** 전역으로 첨부한다.
  // 텍스트는 전역 흡수하지 않는다 — 다른 용도로 복사해 둔 무관한 시크릿이 의도치 않게
  // 분석 대상으로 잡히는 것을 막기 위함(SECURITY_REVIEW 6-2). 텍스트는 붙여넣기 박스에 직접 붙인다.
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const st = useKeylens.getState()
      if (st.screen !== 'app' || st.view !== 'input') return
      const items = e.clipboardData?.items
      if (!items) return
      for (let i = 0; i < items.length; i++) {
        if (items[i].type.startsWith('image')) {
          const f = items[i].getAsFile()
          if (!f) continue
          const rd = new FileReader()
          rd.onload = () => {
            if (typeof rd.result === 'string') useKeylens.getState().handlePasteImage(rd.result)
            else useKeylens.getState().showToast('붙여넣은 이미지를 읽지 못했어요')
          }
          rd.onerror = () => useKeylens.getState().showToast('붙여넣은 이미지를 읽지 못했어요')
          rd.readAsDataURL(f)
          e.preventDefault()
          return
        }
      }
    }
    window.addEventListener('paste', onPaste)
    return () => {
      window.removeEventListener('paste', onPaste)
      useKeylens.getState().cleanup()
    }
  }, [])

  return (
    <>
      {screen === 'offline' && <OfflineScreen />}
      {screen === 'setup' && <SetupScreen />}
      {screen === 'lock' && <LockScreen />}
      {screen === 'app' && (
        <div className="flex min-h-screen bg-bg text-fg">
          <ProjectsDatalist />
          <Sidebar />
          <main className="h-screen min-w-0 flex-1 overflow-y-auto">
            {view === 'input' && <InputScreen />}
            {view === 'vault' && <VaultScreen />}
            {view === 'pending' && <PendingScreen />}
            {view === 'projectAccess' && <ProjectAccessScreen />}
          </main>
        </div>
      )}

      {/* 전역 다이얼로그 · 토스트 */}
      <DeleteModal />
      <DupModal />
      <RotateModal />
      <EnvModal />
      <EnvImportModal />
      <SyncModal />
      <EmailSyncModal />
      <ExplainModal />
      <ResetVaultModal />
      <ForgotResetModal />
      <Toast />
    </>
  )
}
