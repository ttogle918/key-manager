// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT

/** 앱이 다루는 서비스 종류. 지식베이스(SPEC 4.4)가 커지면 확장된다. */
export type Service = 'Notion' | 'Kakao' | 'GCP' | 'OpenAI' | 'Ollama'

/** 최상위 화면 상태. */
export type Screen = 'setup' | 'lock' | 'app'

/** 앱 셸 내부 뷰. */
export type View = 'input' | 'vault'

/** 분류 신뢰도. */
export type Confidence = 'high' | 'mid' | 'low'

/** 서비스별 키 종류 정의 (변수명 매핑 포함). */
export interface TypeOption {
  v: string
  label: string
  var: string
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
