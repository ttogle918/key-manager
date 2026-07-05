// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/** 백엔드 `/analyze` 응답 계약 (backend/app/models.py 와 일치). */

export type ApiConfidence = 'high' | 'medium' | 'low' | 'unknown'

/** Stage2 신호 충돌 시 사용자 선택지. */
export interface ApiConflictOption {
  kind: string
  label: string
  official_env_name: string
  evidence: string
  signal: string
  strong: boolean
}

export interface ClassifiedItem {
  value: string
  masked: string
  service: string | null
  display_name: string | null
  kind: string
  label: string
  official_env_name: string | null
  confidence: ApiConfidence
  format: string
  source: string
  stage: number
  conflict: boolean
  options: ApiConflictOption[]
  meta: Record<string, unknown>
}

export interface AnalyzeApiResponse {
  items: ClassifiedItem[]
  count: number
}

export interface AnalyzeApiRequest {
  text?: string
  url?: string
}

// ── 금고 (VAULT-1/2) 계약 (backend/app/models.py 와 일치) ──

export interface VaultStatus {
  initialized: boolean
  unlocked: boolean
}

export interface VaultEntryCreate {
  service?: string | null
  kind?: string | null
  official_name?: string | null
  value: string
  label?: string | null
  project?: string | null
  memo?: string | null
  expires_at?: string | null
}

export interface VaultEntryUpdate {
  project?: string | null
  memo?: string | null
  expires_at?: string | null
}

/** 값 없는 항목 메타데이터 — 잠금 상태에서도 노출 가능. */
export interface VaultEntryMeta {
  id: number
  service?: string | null
  kind?: string | null
  official_name?: string | null
  label?: string | null
  project?: string | null
  memo?: string | null
  created_at: string
  expires_at?: string | null
}
