// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/** KeyLens 백엔드 클라이언트 (로컬 FastAPI). */
import type {
  AnalyzeApiRequest,
  AnalyzeApiResponse,
  KnowledgeResponse,
  VaultEntryCreate,
  VaultEntryMeta,
  VaultEntryUpdate,
  VaultHistoryEntry,
  VaultBundle,
  VaultImportResult,
  VaultStatus,
  VaultVerifyResult,
} from './types'

/**
 * 백엔드 주소.
 * - dev(`vite`): `http://localhost:8003` (프론트 5173 ↔ 백엔드 8003, 별도 오리진 → CORS)
 * - prod 빌드(데스크톱 앱): 상대 경로('') — SPA와 API를 백엔드가 같은 오리진에서 서빙하므로
 *   포트에 상관없이 same-origin 요청이 되어 CORS가 필요 없다.
 * - 언제든 `VITE_API_BASE` 로 명시 재정의 가능.
 */
const API_BASE = (
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  (import.meta.env.PROD ? '' : 'http://localhost:8003')
).replace(/\/$/, '')

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
    if (!res.ok) {
      // 4xx(입력 문제)와 5xx(서버 문제)를 사용자 언어로 구분.
      if (res.status === 413 || res.status === 422) {
        throw new ApiError('입력이 너무 크거나 형식이 올바르지 않아요 — 줄여서 다시 시도하세요')
      }
      throw new ApiError(`문제가 발생했어요 (오류 ${res.status}) — 잠시 후 다시 시도해 보세요.`)
    }
    return (await res.json()) as AnalyzeApiResponse
  } catch (e) {
    if (e instanceof ApiError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new ApiError('응답이 너무 늦어요 — 다시 시도해 보세요.')
    }
    throw new ApiError('KeyLens에 연결할 수 없어요 — 잠시 후 다시 시도하거나 재시작해 보세요.')
  } finally {
    clearTimeout(timer)
  }
}

/** GET /knowledge — 지식베이스(서비스·종류맵). 실패 시 ApiError(프론트는 기본 맵 유지). */
export async function fetchKnowledge(timeoutMs = 5000): Promise<KnowledgeResponse> {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${API_BASE}/knowledge`, { signal: ctrl.signal })
    if (!res.ok) throw new ApiError(`서비스 목록을 불러오지 못했어요 (오류 ${res.status})`)
    return (await res.json()) as KnowledgeResponse
  } catch (e) {
    if (e instanceof ApiError) throw e
    throw new ApiError('KeyLens에 연결할 수 없어요 — 잠시 후 다시 시도하거나 재시작해 보세요.')
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
    throw new VaultApiError(0, 'KeyLens에 연결할 수 없어요 — 잠시 후 다시 시도하거나 재시작해 보세요.')
  }
  if (!res.ok) {
    let detail = `문제가 발생했어요 (오류 ${res.status}) — 잠시 후 다시 시도해 보세요.`
    try {
      const body = (await res.json()) as { detail?: unknown }
      // FastAPI 자체 검증 오류(예: 비밀번호 8자 미만)는 detail 이 문자열이 아니라
      // [{loc, msg, type}] 배열로 온다 — 그대로 쓰면 토스트에 이상한 값이 뜨니 msg 만 뽑아 쓴다.
      if (typeof body.detail === 'string') {
        detail = body.detail
      } else if (Array.isArray(body.detail) && body.detail.length) {
        const first = body.detail[0] as { msg?: string }
        if (typeof first?.msg === 'string') detail = first.msg
      }
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
  verify: (id: number) =>
    vreq<VaultVerifyResult>(`/vault/entries/${id}/verify`, { method: 'POST' }),
  exportBundle: () => vreq<VaultBundle>('/vault/export', { method: 'POST' }),
  importBundle: (bundle: VaultBundle, password: string, mode: 'replace' | 'merge') =>
    vreq<VaultImportResult>('/vault/import', {
      method: 'POST',
      body: JSON.stringify({ bundle, password, mode }),
    }),
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
