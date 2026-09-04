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
  // 발급 도움말 종류 단위 (GUIDE-1) — 선택
  role?: string | null
  issue_url?: string | null
  docs_url?: string | null
  // 보안 등급·유출 대응 (GUIDE-2) — 선택
  exposure?: 'public' | 'secret' | null
  impact?: string | null
  security_tip?: string | null
}
export interface KnowledgeService {
  service: string
  display_name: string
  // 발급 도움말 서비스 단위 (GUIDE-1) + 종류 구분법 (GUIDE-2)
  console_url?: string | null
  steps?: string[]
  prereq?: string | null
  disambiguation?: string | null
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

/**
 * 평문 메타데이터 수정. **보낸 키만 수정된다** - 생략한 키는 백엔드가 건드리지 않는다.
 * 그래서 컬렉션만 고칠 때 service 를 같이 보내지 않아도 분류가 유지된다.
 * service·kind 는 항상 함께 보내야 한다(둘 다 null 이면 "미지정"으로 되돌림).
 */
export interface VaultEntryUpdate {
  project?: string | null
  memo?: string | null
  expires_at?: string | null
  service?: string | null
  kind?: string | null
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

/** 화면 설명 기능(1단계) 결과 한 항목 — 좌표는 원본 이미지 픽셀 단위. */
export interface ExplainBox {
  x: number
  y: number
  w: number
  h: number
  text: string
  label: string
  tier: 'known' | 'ai_verified' | 'ai_unverified'
  docs_url?: string
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

/** 승인 대기 요청 한 건(RUNTIME-1) — 값 없이 컬렉션·경로 문자열만. */
export interface SdkPendingRequest {
  id: number
  project: string
  path: string
  requested_at: string
}

/** SDK 컬렉션 요약(RUNTIME-1) — 금고에 컬렉션이 지정된 항목이 있으면 자동으로 잡힌다. */
export interface SdkProject {
  project: string
  key_count: number
}

/** SDK 허용 디렉토리 한 건(RUNTIME-1). source: 'manual'(사전 등록) | 'approved'(승인 프롬프트로 등록). */
export interface SdkProjectDir {
  id: number
  path: string
  source: 'manual' | 'approved'
  created_at: string
}

/** 전체 목록(`GET /sdk/directories`)의 한 줄 - 어느 컬렉션 것인지가 함께 온다. */
export interface SdkDirEntryDto extends SdkProjectDir {
  project: string
}
