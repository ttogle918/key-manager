// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * SYNC-2 — Supabase 클라이언트 (옵트인 계정 로그인 기반 금고 동기화).
 *
 * anon(public) key만 쓴다 — Supabase 설계상 클라이언트에 노출돼도 안전하고,
 * 실제 접근 제어는 Postgres RLS(행 수준 보안)가 담당한다. service_role 키는
 * 절대 프론트엔드에 두지 않는다(대시보드 SQL Editor에서 한 번 설정하고 끝).
 *
 * 로그인은 "내 암호화 번들이 서버 어디 있는지" 식별용일 뿐이다 — 복호화 열쇠는
 * 항상 로컬 마스터 비밀번호에서만 유도되고, 서버는 SYNC-0 암호문 번들(.klvault.json)
 * 그대로만 보관한다(제로 널리지 유지). 설계 근거: docs/memo/2026-07-30-sync2-server-sync-decisions.md
 */
import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

/** false면 SYNC-2 UI 자체를 숨긴다 — 설정 안 된 채로 "되는 척"하지 않는다. */
export const supabaseConfigured = Boolean(url && anonKey)

export const supabase: SupabaseClient | null = supabaseConfigured
  ? createClient(url as string, anonKey as string)
  : null
