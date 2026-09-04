// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT

/**
 * 앱이 다루는 서비스의 표시명. 백엔드 `/knowledge`(지식베이스)에서 동적으로 채워지므로
 * 하드코딩 유니온이 아니라 문자열이다 — YAML 한 개만 추가하면 새 서비스가 프론트에도 뜬다.
 */
export type Service = string

/**
 * 최상위 화면 상태.
 *
 * `offline`: 백엔드에 연결하지 못한 상태. **금고 유무를 모르는 상태에서 설정(생성) 화면을
 * 띄우면 안 된다** - 멀쩡히 있는 금고를 잃은 줄 알고 새로 만들려 하게 된다(키 관리 도구에서
 * 이건 꽤 위험한 오해다).
 */
export type Screen = 'setup' | 'lock' | 'app' | 'offline'

/** 앱 셸 내부 뷰. */
export type View = 'input' | 'vault' | 'pending' | 'projectAccess'

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
  /** 사용자가 정한 환경변수명. 비어 있으면 종류(typeKey)에서 도출한 공식 이름을 쓴다. */
  varName?: string
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
  /**
   * 평문 값. **보관함 화면에서는 절대 채우지 않는다** - 내보내기(`withValues`)가
   * 만드는 임시 복사본에서만 쓰인다. 화면 표시는 아래 `preview` 를 쓴다.
   */
  full: string
  /**
   * 값 공개 시 보여줄 **앞뒤 4글자만 남긴 문자열**(`mask(v, 4, 4)`).
   *
   * 화면에서 확인해야 하는 건 "이게 그 키가 맞나"이지 값 전체가 아니다. 표시에 쓰지도
   * 않는 평문을 스토어에 들고 있을 이유가 없어서, 복호화 결과를 여기로만 넣는다.
   * (스토어를 암호화하는 건 의미가 없다 - 복호화 키도 같은 메모리에 있어야 하므로.
   * 실효 있는 대책은 평문을 아예 두지 않는 것이다. 디스크 암호화는 백엔드가 담당한다.)
   */
  preview?: string
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

/** SDK 컬렉션 요약(RUNTIME-1, 프론트 내부 표현). */
export interface SdkProjectSummary {
  project: string
  keyCount: number
}

/** SDK 허용 디렉토리 한 건(RUNTIME-1, 프론트 내부 표현). */
export interface SdkDir {
  id: number
  path: string
  source: 'manual' | 'approved'
  createdAt: string
}

/** 허용 디렉토리 한 건 + 어느 컬렉션 것인지(전체 목록용, RUNTIME-1). */
export interface SdkDirEntry extends SdkDir {
  project: string
}

/** `.env` 가져오기 표의 한 줄. 저장 전 상태라 값이 평문으로 들어 있다. */
export interface EnvImportRow {
  id: string
  /** 환경변수명. `.env` 원본 이름이 기본값 - 사용자가 고칠 수 있다. */
  name: string
  value: string
  checked: boolean
  /** /analyze 가 알아본 서비스 id. 못 알아봤으면 null. */
  service: string | null
  /** /analyze 가 알아본 종류 키(예: "pat"). 못 알아봤으면 null. */
  kind: string | null
  /** 종류 라벨(예: "Personal Access Token"). 못 알아봤으면 null. */
  typeLabel: string | null
  /** 지식베이스 공식 이름이 원본과 다를 때만 채워진다 - "제안"으로 보여준다. */
  suggestedName: string | null
}
