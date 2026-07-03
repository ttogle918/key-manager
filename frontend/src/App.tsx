// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect } from 'react'
import { useKeylens } from '@/store/keylensStore'
import { Sidebar } from '@/components/Sidebar'
import { SetupScreen } from '@/components/screens/SetupScreen'
import { LockScreen } from '@/components/screens/LockScreen'
import { InputScreen } from '@/components/screens/InputScreen'
import { VaultScreen } from '@/components/screens/VaultScreen'
import { DeleteModal, DupModal, EnvModal } from '@/components/modals/Modals'
import { Toast } from '@/components/ui/Toast'
import { ProjectsDatalist } from '@/components/ProjectsDatalist'

export default function App() {
  const screen = useKeylens((s) => s.screen)
  const view = useKeylens((s) => s.view)

  // 전역 붙여넣기: 입력 화면에서 이미지는 첨부, 텍스트는 붙여넣기 영역으로.
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
          rd.onload = () => useKeylens.getState().handlePasteImage(rd.result as string)
          rd.readAsDataURL(f)
          e.preventDefault()
          return
        }
      }
      const tag = (e.target as HTMLElement | null)?.tagName
      if (tag !== 'INPUT' && tag !== 'TEXTAREA' && !st.analyzed && !st.analyzing) {
        const txt = e.clipboardData?.getData('text')
        if (txt) st.handlePasteText(txt)
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
      {screen === 'setup' && <SetupScreen />}
      {screen === 'lock' && <LockScreen />}
      {screen === 'app' && (
        <div className="flex min-h-screen bg-bg text-fg">
          <ProjectsDatalist />
          <Sidebar />
          <main className="h-screen min-w-0 flex-1 overflow-y-auto">
            {view === 'input' ? <InputScreen /> : <VaultScreen />}
          </main>
        </div>
      )}

      {/* 전역 다이얼로그 · 토스트 */}
      <DeleteModal />
      <DupModal />
      <EnvModal />
      <Toast />
    </>
  )
}
