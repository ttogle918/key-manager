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

/**
 * POST /sync/request - 확인 메일 발송을 요청하고 **확인 코드**를 돌려받는다.
 *
 * 코드는 메일에 들어 있지 않다. 앱 화면에만 뜨고, 사용자가 확인 페이지에 그걸 입력해야
 * 실제 파일이 발송된다. 메일함을 가진 사람이 아니라 요청을 시작한 사람만 발송을 끝낼 수
 * 있게 하려는 것이다 - 수신 주소를 오타 냈을 때 낯선 사람이 링크만으로 번들을 받아가는
 * 걸 막는다(메일 보안 스캐너의 링크 자동 열람도 같은 이유로 막힌다).
 */
export async function requestEmailExport(
  destinationEmail: string,
  bundle: unknown,
  // 서버(manager-relay/app/mailer.py)의 SMTP 발송은 smtplib timeout=10(초) 로 연결을 시도한다.
  // 여기에 연결/TLS/로그인 오버헤드까지 더하면 서버의 최악 케이스가 10초를 넘을 수 있으므로,
  // 클라이언트 타임아웃을 그보다 넉넉히 길게 잡아 실제로는 성공한 발송을 스푸리어스
  // "응답이 너무 늦어요" 에러로 오탐하지 않게 한다.
  timeoutMs = 20000,
): Promise<string> {
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
    const body = (await res.json()) as { code?: unknown }
    if (typeof body.code !== 'string' || !/^[0-9]{6}$/.test(body.code)) {
      // 코드 없이 진행하면 사용자가 확인 페이지에서 넣을 게 없어 발송이 영영 끝나지 않는다.
      // 구버전 릴레이에 붙었을 때 조용히 반쪽으로 도는 것보다 여기서 멈추는 게 낫다.
      throw new SyncRelayError('릴레이 서버가 확인 코드를 주지 않았어요 — 서버를 최신으로 올려주세요.')
    }
    return body.code
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
