// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}
interface State {
  error: Error | null
}

/**
 * 예기치 못한 렌더/라이프사이클 에러를 잡아 흰 화면(크래시) 대신 복구 UI를 보여준다(OSS-1).
 * 값·시크릿은 표시하지 않는다 — 에러 메시지만.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error) {
    // 로컬 도구라 외부 전송 없이 콘솔에만 기록.
    console.error('[KeyLens] 렌더 오류:', error)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg px-6 text-fg">
        <div className="max-w-[420px] text-center">
          <div className="text-[17px] font-bold">문제가 발생했어요</div>
          <p className="mt-3 text-[13px] leading-[1.6] text-muted">
            화면을 그리는 중 예기치 못한 오류가 났습니다. 값·비밀번호는 안전하며, 이 화면에 노출되지 않습니다.
            <br />
            새로고침하면 잠금 화면부터 다시 시작합니다.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 cursor-pointer rounded-lg border-none bg-mint px-[16px] py-2 text-[12.5px] font-bold text-[#05231A] hover:brightness-[1.07]"
          >
            새로고침
          </button>
          <details className="mt-4 text-left text-[11px] text-dim-2">
            <summary className="cursor-pointer">기술 정보</summary>
            <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all font-mono">
              {this.state.error.message}
            </pre>
          </details>
        </div>
      </div>
    )
  }
}
