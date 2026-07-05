// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/** 백엔드 `/analyze` 응답 계약 (backend/app/models.py 와 일치). */

export type ApiConfidence = 'high' | 'medium' | 'low' | 'unknown'

/** `GET /knowledge` — 지식베이스(서비스·종류맵)를 프론트가 동적으로 구성한다. */
export interface KnowledgeCredential {
  kind: string
  label: string
  official_env_name: string
  value_based: boolean
  expiry_known: boolean
  verifiable: boolean
}
export interface KnowledgeService {
  service: string
  display_name: string
  credentials: KnowledgeCredential[]
}
export interface KnowledgeResponse {
  services: KnowledgeService[]
}

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

/** 감사 이력 한 줄(값 없음) — 등록·열람·복사·내보내기. */
export interface VaultHistoryEntry {
  date: string
  event: string
}

/** 키 유효성 검증 결과(TRUST-1) — 값 없이 상태만. */
export interface VaultVerifyResult {
  status: 'active' | 'invalid' | 'unknown' | 'unsupported'
  detail: string
}

/** 암호화 금고 번들(SYNC-0) — 전부 암호문·KDF 파라미터. 평문/키 없음. */
export interface VaultBundle {
  format: string
  version: number
  exported_at?: string
  kdf: Record<string, unknown>
  verifier: Record<string, unknown>
  entries: unknown[]
}

/** 가져오기 결과(SYNC-0) — 값 없이 개수만. */
export interface VaultImportResult {
  imported: number
  skipped: number
  mode: string
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
