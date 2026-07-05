// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { Confidence, Service, SvcMeta, TypeOption } from '@/types'

/**
 * 서비스별 키 종류 → 공식 환경변수명 매핑 (SPEC 4.4 지식베이스의 프론트 표현).
 * 실제 구현에선 백엔드가 YAML에서 로드하지만, 현재는 목업으로 여기에 둔다.
 */
export const TYPE_MAP: Record<Service, TypeOption[]> = {
  Notion: [
    { v: 'api', label: 'API Key', var: 'NOTION_API_KEY' },
    { v: 'db', label: 'Database ID', var: 'NOTION_DATABASE_ID' },
    { v: 'ds', label: 'Data Source ID', var: 'NOTION_DATA_SOURCE_ID' },
    { v: 'page', label: 'Page ID', var: 'NOTION_PAGE_ID' },
  ],
  OpenAI: [
    { v: 'api', label: 'API Key', var: 'OPENAI_API_KEY' },
    { v: 'org', label: 'Organization ID', var: 'OPENAI_ORG_ID' },
  ],
  Kakao: [
    { v: 'rest', label: 'REST API 키', var: 'KAKAO_REST_API_KEY' },
    { v: 'js', label: 'JavaScript 키', var: 'KAKAO_JS_KEY' },
    { v: 'admin', label: 'Admin 키', var: 'KAKAO_ADMIN_KEY' },
    { v: 'native', label: 'Native 앱 키', var: 'KAKAO_NATIVE_APP_KEY' },
  ],
  GCP: [{ v: 'api', label: 'API Key', var: 'GOOGLE_API_KEY' }],
  Ollama: [{ v: 'api', label: 'API Key', var: 'OLLAMA_API_KEY' }],
}

/** 서비스 타일(약자 + 색). */
export const SVC_META: Record<Service, SvcMeta> = {
  Notion: { tile: 'N', bg: '#E7EAEE', fg: '#15181D' },
  Kakao: { tile: 'K', bg: '#F2D14B', fg: '#241D00' },
  GCP: { tile: 'G', bg: '#4E8DF5', fg: '#FFFFFF' },
  OpenAI: { tile: 'O', bg: '#17B597', fg: '#03211B' },
  Ollama: { tile: 'Ol', bg: '#111418', fg: '#FFFFFF' },
}

/** 보관함/내보내기에서 사용하는 서비스 표시 순서. */
export const SERVICE_ORDER: Service[] = ['Notion', 'Kakao', 'GCP', 'OpenAI', 'Ollama']

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
