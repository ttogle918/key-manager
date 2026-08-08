// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT

/**
 * 앱이 다루는 서비스의 표시명. 백엔드 `/knowledge`(지식베이스)에서 동적으로 채워지므로
 * 하드코딩 유니온이 아니라 문자열이다 — YAML 한 개만 추가하면 새 서비스가 프론트에도 뜬다.
 */
export type Service = string

/** 최상위 화면 상태. */
export type Screen = 'setup' | 'lock' | 'app'

/** 앱 셸 내부 뷰. */
export type View = 'input' | 'vault' | 'pending'

/** 분석·입력 화면의 두 입력 모드 — 자동 분류(기존) vs 직접 입력(신규). */
export type InputMode = 'auto' | 'manual'

/** 직접 입력 탭의 한 행(저장 전 이름=값 쌍). */
export interface ManualRow {
  id: string
  name: string
  value: string
}

/** 분류 신뢰도. */
export type Confidence = 'high' | 'mid' | 'low'

/** 서비스별 키 종류 정의 (변수명 매핑 + 발급 도움말 GUIDE-1). */
export interface TypeOption {
  v: string
  label: string
  var: string
  /** 발급 도움말 종류 단위 (선택) — /knowledge 에서 채워짐. */
  role?: string | null
  issueUrl?: string | null
  docsUrl?: string | null
  /** 보안 등급·유출 대응 (GUIDE-2). */
  exposure?: 'public' | 'secret' | null
  impact?: string | null
  securityTip?: string | null
}

/** UUID 신호 충돌 시 사용자가 고르는 후보. */
export interface ConflictOption {
  k: string
  label: string
  varName: string
  evidence: string
  signal: string
  strong: boolean
}

/** 분석 결과 카드 한 건 (아직 보관함에 저장되기 전). */
export interface AnalysisResult {
  id: string
  service: Service
  typeKey: string
  conf: Confidence
  masked: string
  full: string
  format: string
  source: string
  context?: string
  midNote?: string
  conflict?: boolean
  options?: ConflictOption[]
  memo: string
  project: string
  metaOpen: boolean
  meta: Record<string, unknown>
  dupNote?: string | null
  /** OCR 이 이어붙인 값의 이음매 글자 인덱스(불확실 — 사용자 확인용). 없으면 undefined. */
  ocrUncertain?: number[]
}

/** 회전/등록 등 키 이력 한 줄. */
export interface HistoryEntry {
  date: string
  event: string
}

/** 키 유효성 검증 상태(TRUST-1) — 값은 담지 않고 상태만. */
export type VerifyStatus = 'active' | 'invalid' | 'unknown' | 'unsupported'

/** 검증 결과 + 진행 표시(프론트 전용, 저장 안 됨). */
export interface VerifyState {
  status: VerifyStatus
  detail: string
  checking?: boolean
}

/** 보관함에 암호화되어 저장된 자격증명 한 건. */
export interface VaultItem {
  id: string
  service: Service
  type: string
  varName: string
  masked: string
  full: string
  addedAt: string
  project: string
  context: string
  memo: string
  /** 원본 스크린샷 data URL, 'sample'(더미), 또는 null. */
  sourceImage: string | null
  expiresAt: string | null
  history: HistoryEntry[]
  meta: Record<string, unknown>
  /** 키 유효성 검증 결과(TRUST-1) — 명시적 검증 전엔 undefined. */
  verify?: VerifyState
}

/** 서비스 타일 표시용 메타(약자 + 색). */
export interface SvcMeta {
  tile: string
  bg: string
  fg: string
}

/** Stage1에서 값만으로 판별 불가한 항목(서비스 미상). Stage2(맥락)로 넘어갈 후보. */
export interface UnknownItem {
  keyName: string
  masked: string
  format: string
  source: string
}

/** 삭제 확인 대상. */
export type DeleteTarget = VaultItem | null

/** 중복 감지 대상. */
export interface DupTarget {
  resultId: string
  existing: VaultItem
  varName: string
}

/** 승인 대기 요청 한 건(RUNTIME-1, 프론트 내부 표현). */
export interface PendingRequest {
  id: number
  project: string
  path: string
  requestedAt: string
}
