// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/** KeyLens 백엔드 클라이언트 (로컬 FastAPI). */
import type { AnalyzeApiRequest, AnalyzeApiResponse } from './types'

/** 백엔드 주소. 기본 로컬 8003, 필요 시 VITE_API_BASE 로 재정의. */
const API_BASE =
  ((import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8003').replace(
    /\/$/,
    '',
  )

/** 백엔드가 응답하지 않거나 오류일 때 던지는 에러. */
export class ApiError extends Error {}

/** POST /analyze — 타임아웃·네트워크 오류를 ApiError 로 정규화한다. */
export async function analyzeApi(
  req: AnalyzeApiRequest,
  timeoutMs = 8000,
): Promise<AnalyzeApiResponse> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
      signal: ctrl.signal,
    })
    if (!res.ok) throw new ApiError(`백엔드 오류 (${res.status})`)
    return (await res.json()) as AnalyzeApiResponse
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('백엔드 응답 시간 초과')
    }
    throw new ApiError('백엔드에 연결할 수 없습니다')
  } finally {
    clearTimeout(timer)
  }
}
