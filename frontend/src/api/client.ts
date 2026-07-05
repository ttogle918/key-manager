// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/** KeyLens 백엔드 클라이언트 (로컬 FastAPI). */
import type {
  AnalyzeApiRequest,
  AnalyzeApiResponse,
  VaultEntryCreate,
  VaultEntryMeta,
  VaultEntryUpdate,
  VaultHistoryEntry,
  VaultStatus,
} from './types'

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

// ── 금고 (VAULT-1/2) ──────────────────────────────────────────────

/** 금고 API 오류 — HTTP 상태를 담아 401(잠금)·429(지연)·409(충돌)를 구분한다. status=0 은 네트워크 실패. */
export class VaultApiError extends Error {
  readonly status: number
  readonly retryAfter?: number
  constructor(status: number, message: string, retryAfter?: number) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

async function vreq<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new VaultApiError(0, '백엔드에 연결할 수 없습니다')
  }
  if (!res.ok) {
    let detail = `금고 오류 (${res.status})`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      /* 본문 없음 */
    }
    const retry = Number(res.headers.get('Retry-After')) || undefined
    throw new VaultApiError(res.status, detail, retry)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const vaultApi = {
  status: () => vreq<VaultStatus>('/vault/status'),
  init: (password: string) =>
    vreq<VaultStatus>('/vault/init', { method: 'POST', body: JSON.stringify({ password }) }),
  unlock: (password: string) =>
    vreq<VaultStatus>('/vault/unlock', { method: 'POST', body: JSON.stringify({ password }) }),
  lock: () => vreq<VaultStatus>('/vault/lock', { method: 'POST' }),
  list: () => vreq<VaultEntryMeta[]>('/vault/entries'),
  add: (entry: VaultEntryCreate) =>
    vreq<VaultEntryMeta>('/vault/entries', { method: 'POST', body: JSON.stringify(entry) }),
  value: (id: number, event: 'reveal' | 'copy' | 'export' = 'reveal') =>
    vreq<{ value: string }>(`/vault/entries/${id}/value?event=${event}`),
  history: (id: number) => vreq<VaultHistoryEntry[]>(`/vault/entries/${id}/history`),
  update: (id: number, patch: VaultEntryUpdate) =>
    vreq<VaultEntryMeta>(`/vault/entries/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  rotate: (id: number, value: string) =>
    vreq<VaultEntryMeta>(`/vault/entries/${id}/rotate`, {
      method: 'POST',
      body: JSON.stringify({ value }),
    }),
  remove: (id: number) =>
    vreq<VaultStatus>(`/vault/entries/${id}`, { method: 'DELETE' }),
  changePassword: (oldPassword: string, newPassword: string) =>
    vreq<VaultStatus>('/vault/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }),
}
