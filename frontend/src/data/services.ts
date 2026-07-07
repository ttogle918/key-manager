// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { KnowledgeResponse } from '@/api/types'
import type { Confidence, SvcMeta, TypeOption } from '@/types'

/**
 * 서비스 레지스트리 — 백엔드 `GET /knowledge`(지식베이스)에서 **런타임에** 채워진다.
 * 아래 값들은 백엔드 미연결 시의 폴백(기본 5종)이며, `applyKnowledge()`가 실제 KB로 교체한다.
 * ES 모듈 라이브 바인딩이라, 교체 후 이 심볼들을 import 한 모든 곳이 갱신된 맵을 읽는다.
 *
 * `TypeOption.v`(typeKey)는 백엔드 `kind`와 동일하게 맞춘다 — 프론트 내부 매칭 키로만 쓰고
 * 새 서비스가 와도 `/knowledge`가 주는 kind 그대로 사용하므로 하드코딩이 필요 없다.
 */
export let TYPE_MAP: Record<string, TypeOption[]> = {
  Notion: [
    { v: 'api_key', label: 'API Key', var: 'NOTION_API_KEY' },
    { v: 'database_id', label: 'Database ID', var: 'NOTION_DATABASE_ID' },
    { v: 'data_source_id', label: 'Data Source ID', var: 'NOTION_DATA_SOURCE_ID' },
    { v: 'page_id', label: 'Page ID', var: 'NOTION_PAGE_ID' },
  ],
  OpenAI: [
    { v: 'api_key', label: 'API Key', var: 'OPENAI_API_KEY' },
    { v: 'org_id', label: 'Organization ID', var: 'OPENAI_ORG_ID' },
  ],
  Kakao: [
    { v: 'rest_api_key', label: 'REST API 키', var: 'KAKAO_REST_API_KEY' },
    { v: 'javascript_key', label: 'JavaScript 키', var: 'KAKAO_JS_KEY' },
    { v: 'admin_key', label: 'Admin 키', var: 'KAKAO_ADMIN_KEY' },
    { v: 'native_app_key', label: 'Native 앱 키', var: 'KAKAO_NATIVE_APP_KEY' },
  ],
  GCP: [{ v: 'api_key', label: 'API Key', var: 'GOOGLE_API_KEY' }],
  Ollama: [{ v: 'api_key', label: 'API Key', var: 'OLLAMA_API_KEY' }],
}

/** 서비스 타일(약자 + 색). 알려진 서비스는 큐레이션 값을, 새 서비스는 자동 생성한다. */
export let SVC_META: Record<string, SvcMeta> = {
  Notion: { tile: 'N', bg: '#E7EAEE', fg: '#15181D' },
  Kakao: { tile: 'K', bg: '#F2D14B', fg: '#241D00' },
  GCP: { tile: 'G', bg: '#4E8DF5', fg: '#FFFFFF' },
  OpenAI: { tile: 'O', bg: '#17B597', fg: '#03211B' },
  Ollama: { tile: 'Ol', bg: '#111418', fg: '#FFFFFF' },
}

/** 보관함/내보내기에서 사용하는 서비스 표시 순서. */
export let SERVICE_ORDER: string[] = ['Notion', 'Kakao', 'GCP', 'OpenAI', 'Ollama']

/** 프론트 표시명 → 백엔드 service id (금고 저장 시). */
export let SERVICE_TO_ID: Record<string, string> = {
  Notion: 'notion',
  Kakao: 'kakao',
  GCP: 'gcp',
  OpenAI: 'openai',
  Ollama: 'ollama',
}

/** 백엔드 service id → 프론트 표시명 (SVC_META·TYPE_MAP 키). */
export let SERVICE_BY_ID: Record<string, string> = {
  notion: 'Notion',
  kakao: 'Kakao',
  gcp: 'GCP',
  openai: 'OpenAI',
  ollama: 'Ollama',
}

/** 서비스 표시명 → 발급 도움말(서비스 단위, GUIDE-1). /knowledge 로 채워짐. */
export let CONSOLE_URL: Record<string, string | null> = {}
export let SVC_STEPS: Record<string, string[]> = {}
export let SVC_PREREQ: Record<string, string | null> = {}
/** 종류 구분법 (GUIDE-2) — 신호 충돌 카드에 표시. */
export let SVC_DISAMBIG: Record<string, string | null> = {}
/** 발급/문서 링크로 허용되는 호스트(지식베이스가 선언한 도메인만). 오픈 리다이렉트 방지. */
export let ALLOWED_HOSTS: Set<string> = new Set()

// 알려진 서비스의 큐레이션된 외양(id 기준). 없으면 autoMeta 로 자동 생성.
const CURATED_META: Record<string, SvcMeta> = {
  notion: { tile: 'N', bg: '#E7EAEE', fg: '#15181D' },
  kakao: { tile: 'K', bg: '#F2D14B', fg: '#241D00' },
  gcp: { tile: 'G', bg: '#4E8DF5', fg: '#FFFFFF' },
  openai: { tile: 'O', bg: '#17B597', fg: '#03211B' },
  ollama: { tile: 'Ol', bg: '#111418', fg: '#FFFFFF' },
}
// 큐레이션 서비스의 표시 순서(id). 나머지는 뒤에 알파벳순으로 붙는다.
const CURATED_ORDER = ['notion', 'kakao', 'gcp', 'openai', 'ollama']
// 새 서비스 타일 자동 색(어두운 배경 + 흰 글자로 가독성 확보).
const AUTO_PALETTE: Array<{ bg: string; fg: string }> = [
  { bg: '#3B5BDB', fg: '#FFFFFF' },
  { bg: '#2F9E44', fg: '#FFFFFF' },
  { bg: '#E8590C', fg: '#FFFFFF' },
  { bg: '#9C36B5', fg: '#FFFFFF' },
  { bg: '#0C8599', fg: '#FFFFFF' },
  { bg: '#C2255C', fg: '#FFFFFF' },
]
function autoMeta(name: string): SvcMeta {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  const p = AUTO_PALETTE[h % AUTO_PALETTE.length]
  return { tile: name.slice(0, 2), bg: p.bg, fg: p.fg }
}

/**
 * `/knowledge` 응답으로 레지스트리 전체를 교체한다. 새 서비스는 YAML 하나만 추가하면
 * 여기서 자동 반영된다(프론트 코드 수정 0). 큐레이션 외양이 없는 서비스는 색·타일을 자동 부여.
 */
export function applyKnowledge(payload: KnowledgeResponse): void {
  const typeMap: Record<string, TypeOption[]> = {}
  const svcMeta: Record<string, SvcMeta> = {}
  const toId: Record<string, string> = {}
  const byId: Record<string, string> = {}
  const consoleUrl: Record<string, string | null> = {}
  const steps: Record<string, string[]> = {}
  const prereq: Record<string, string | null> = {}
  const disambig: Record<string, string | null> = {}
  const hosts = new Set<string>()
  const addHost = (u?: string | null) => {
    if (!u) return
    try {
      hosts.add(new URL(u).host)
    } catch {
      /* 파싱 불가 URL은 허용 목록에 넣지 않음 */
    }
  }
  for (const s of payload.services) {
    const name = s.display_name
    addHost(s.console_url)
    for (const c of s.credentials) {
      addHost(c.issue_url)
      addHost(c.docs_url)
    }
    typeMap[name] = s.credentials.map((c) => ({
      v: c.kind,
      label: c.label,
      var: c.official_env_name,
      role: c.role ?? null,
      issueUrl: c.issue_url ?? null,
      docsUrl: c.docs_url ?? null,
      exposure: c.exposure ?? null,
      impact: c.impact ?? null,
      securityTip: c.security_tip ?? null,
    }))
    svcMeta[name] = CURATED_META[s.service] ?? autoMeta(name)
    toId[name] = s.service
    byId[s.service] = name
    consoleUrl[name] = s.console_url ?? null
    steps[name] = s.steps ?? []
    prereq[name] = s.prereq ?? null
    disambig[name] = s.disambiguation ?? null
  }
  const rank = (id: string) => {
    const i = CURATED_ORDER.indexOf(id)
    return i < 0 ? CURATED_ORDER.length : i
  }
  SERVICE_ORDER = payload.services
    .slice()
    .sort(
      (a, b) =>
        rank(a.service) - rank(b.service) || a.display_name.localeCompare(b.display_name),
    )
    .map((s) => s.display_name)
  TYPE_MAP = typeMap
  SVC_META = svcMeta
  SERVICE_TO_ID = toId
  SERVICE_BY_ID = byId
  CONSOLE_URL = consoleUrl
  SVC_STEPS = steps
  SVC_PREREQ = prereq
  SVC_DISAMBIG = disambig
  ALLOWED_HOSTS = hosts
}

// ── GUIDE-1 B: 발급 링크 딥링크 해석(플레이스홀더 치환) + 도메인 화이트리스트 ──

// 프로젝트/앱 ID 로 인정할 형태(공백·한글 라벨은 제외 → 치환하지 않고 폴백).
const ID_LIKE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$/
const PLACEHOLDER = /\{[a-z_]+\}/i

/** https + 지식베이스 선언 호스트만 허용(javascript:·외부 도메인 차단). */
export function isAllowedUrl(u: string | null | undefined): boolean {
  if (!u) return false
  try {
    const url = new URL(u)
    return url.protocol === 'https:' && ALLOWED_HOSTS.has(url.host)
  } catch {
    return false
  }
}

/** 플레이스홀더가 남은 쿼리 파라미터를 제거(치환 못 하면 깨진 링크 대신 기본 콘솔로). */
function stripPlaceholders(u: string): string {
  try {
    const url = new URL(u)
    const keep = new URLSearchParams()
    url.searchParams.forEach((v, k) => {
      if (!PLACEHOLDER.test(v)) keep.set(k, v)
    })
    url.search = keep.toString()
    // 경로에 남은 플레이스홀더가 있으면 콘솔 루트로 안전 폴백
    return PLACEHOLDER.test(url.pathname) ? url.origin + '/' : url.toString()
  } catch {
    return u.split('?')[0]
  }
}

/**
 * 발급 URL 을 항목 컨텍스트로 해석한다.
 * - `project` 가 ID 형태면 `{project}`/`{project_id}`/`{app_id}` 를 치환해 **딥링크**
 * - 아니면 플레이스홀더를 제거해 **기본 콘솔**로 폴백(깨진 링크 방지)
 * - 최종 URL 이 화이트리스트(https + 선언 호스트)를 통과할 때만 반환, 아니면 null
 */
export function resolveIssueUrl(
  url: string | null | undefined,
  project?: string | null,
): string | null {
  if (!url) return null
  let out = url
  if (project && ID_LIKE.test(project)) {
    out = out.replace(/\{(project|project_id|app_id)\}/gi, encodeURIComponent(project))
  }
  if (PLACEHOLDER.test(out)) out = stripPlaceholders(out)
  return isAllowedUrl(out) ? out : null
}

export interface ConfStyle {
  label: string
  bg: string
  fg: string
  border: string
}

/** 신뢰도 뱃지 스타일. 'manual'은 충돌을 사용자가 수동 확정한 경우. */
export const CONF_META: Record<Confidence | 'manual', ConfStyle> = {
  high: {
    label: '신뢰도 높음',
    bg: 'rgba(62,207,142,.1)',
    fg: '#5FD9A4',
    border: 'rgba(62,207,142,.28)',
  },
  mid: {
    label: '신뢰도 중간',
    bg: 'rgba(143,163,191,.12)',
    fg: '#9FB2CC',
    border: 'rgba(143,163,191,.25)',
  },
  low: {
    label: '확인 필요',
    bg: 'rgba(227,179,65,.13)',
    fg: '#E3B341',
    border: 'rgba(227,179,65,.35)',
  },
  manual: {
    label: '확인됨 · 수동',
    bg: 'rgba(62,207,142,.1)',
    fg: '#5FD9A4',
    border: 'rgba(62,207,142,.28)',
  },
}
