// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * SYNC-2(재설계) — 이메일 릴레이 동기화 클라이언트.
 *
 * 릴레이 서버 주소는 비밀이 아니다(공개 URL일 뿐) — 실제 자격증명(SMTP)은 그 릴레이
 * 서버 자신의 배포 환경변수에만 있고, 이 프론트/exe에는 절대 들어오지 않는다.
 * 설계 근거: docs/superpowers/specs/2026-08-26-sync2-email-relay-design.md
 */
const RELAY_URL = (import.meta.env.VITE_SYNC_RELAY_URL as string | undefined)?.replace(/\/$/, '')

/** false면 이메일 동기화 UI 자체를 숨긴다 — 설정 안 된 채로 "되는 척"하지 않는다. */
export const syncRelayConfigured = Boolean(RELAY_URL)

export class SyncRelayError extends Error {}

/** POST /sync/request — 확인 메일 발송을 요청한다(실제 첨부는 사용자가 그 메일의 링크를 눌러야 감). */
export async function requestEmailExport(
  destinationEmail: string,
  bundle: unknown,
  timeoutMs = 10000,
): Promise<void> {
  if (!RELAY_URL) throw new SyncRelayError('이메일 동기화가 설정되지 않았어요')
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeoutMs)
  try {
    const res = await fetch(`${RELAY_URL}/sync/request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination_email: destinationEmail, bundle }),
      signal: ctrl.signal,
    })
    if (!res.ok) {
      if (res.status === 429) {
        throw new SyncRelayError('요청이 너무 많아요 — 잠시 후 다시 시도하세요')
      }
      throw new SyncRelayError(`문제가 발생했어요 (오류 ${res.status}) — 잠시 후 다시 시도해 보세요.`)
    }
  } catch (e) {
    if (e instanceof SyncRelayError) throw e
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new SyncRelayError('응답이 너무 늦어요 — 다시 시도해 보세요.')
    }
    throw new SyncRelayError('이메일 동기화 서버에 연결할 수 없어요 — 잠시 후 다시 시도하세요.')
  } finally {
    clearTimeout(timer)
  }
}
