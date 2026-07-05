// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/** 백엔드 분류 결과(ClassifiedItem)를 프론트 도메인(AnalysisResult)으로 변환. */
import { SERVICE_BY_ID, TYPE_MAP } from '@/data/services'
import type { AnalysisResult, Confidence, UnknownItem, VaultItem } from '@/types'
import type { ApiConfidence, ClassifiedItem, VaultEntryMeta } from './types'

// 레지스트리(지식베이스 기반)에서 온 id↔표시명 맵을 재노출 — 저장 경로가 그대로 쓴다.
export { SERVICE_TO_ID } from '@/data/services'

/** 잠금 상태에서 값을 모르므로 표시용 자리표시 마스크. 값 공개 시 실제 값으로 대체된다. */
const MASK_PLACEHOLDER = '••••••••••••'

/**
 * 백엔드 금고 항목 메타데이터 → 프론트 VaultItem. 값(full)은 잠금/미공개 상태라 비어 있고,
 * 공개(reveal) 시 복호화 값을 채운다. context·history·sourceImage 는 백엔드 미저장 → 비움.
 */
export function metaToVaultItem(m: VaultEntryMeta): VaultItem {
  const svc = (m.service && SERVICE_BY_ID[m.service]) || 'OpenAI'
  const typeDef = m.official_name
    ? TYPE_MAP[svc]?.find((t) => t.var === m.official_name)
    : undefined
  return {
    id: String(m.id),
    service: svc,
    type: m.label || typeDef?.label || m.kind || '',
    varName: m.official_name || '',
    masked: MASK_PLACEHOLDER,
    full: '',
    addedAt: (m.created_at || '').slice(0, 10),
    project: m.project || '',
    context: '',
    memo: m.memo || '',
    sourceImage: null,
    expiresAt: m.expires_at || null,
    history: [],
    meta: {},
  }
}

/** 백엔드 confidence → 프론트 conf. */
const CONF_BY_API: Record<ApiConfidence, Confidence> = {
  high: 'high',
  medium: 'mid',
  low: 'low',
  unknown: 'low',
}

export interface MappedResults {
  results: AnalysisResult[]
  unknowns: UnknownItem[]
}

/** meta에서 사람이 읽을 컨텍스트 한 줄을 뽑는다(있으면). */
function contextFrom(meta: Record<string, unknown>): string | undefined {
  for (const key of ['label', 'ocr_title', 'shell_line', 'console_tab', 'workspace']) {
    const v = meta[key]
    if (typeof v === 'string' && v) return v
  }
  return undefined
}

/**
 * 서비스가 확정된 항목은 AnalysisResult 카드로,
 * 값만으로 판별 불가한 항목(service=null)은 unknowns 로 분리한다.
 * 조인 키는 official_env_name — 백엔드/프론트가 공유하는 안정적 계약.
 */
export function toAnalysisResults(
  items: ClassifiedItem[],
  memo: string,
  project: string,
): MappedResults {
  const results: AnalysisResult[] = []
  const unknowns: UnknownItem[] = []

  items.forEach((it, i) => {
    const svc = it.service ? SERVICE_BY_ID[it.service] : undefined

    // Stage2 신호 충돌 → 프론트 충돌 카드(사용자가 종류 선택). option.k = 프론트 typeKey.
    if (it.conflict && svc) {
      results.push({
        id: `api_${i}`,
        service: svc,
        typeKey: '',
        conflict: true,
        conf: 'low',
        masked: it.masked,
        full: it.value,
        format: it.format,
        source: it.source,
        context: contextFrom(it.meta),
        memo,
        project,
        metaOpen: false,
        meta: it.meta,
        options: it.options.map((o) => ({
          k: TYPE_MAP[svc].find((t) => t.var === o.official_env_name)?.v ?? '',
          label: o.label,
          varName: o.official_env_name,
          evidence: o.evidence,
          signal: o.signal,
          strong: o.strong,
        })),
      })
      return
    }

    if (svc && it.official_env_name) {
      const typeDef = TYPE_MAP[svc].find((t) => t.var === it.official_env_name)
      results.push({
        id: `api_${i}`,
        service: svc,
        typeKey: typeDef ? typeDef.v : '',
        conf: CONF_BY_API[it.confidence] ?? 'low',
        masked: it.masked,
        full: it.value,
        format: it.format,
        source: it.source,
        context: contextFrom(it.meta),
        memo,
        project,
        metaOpen: false,
        meta: it.meta,
      })
    } else {
      const assigned = it.meta['assigned_name']
      unknowns.push({
        keyName: typeof assigned === 'string' && assigned ? assigned : '(변수명 미상)',
        masked: it.masked,
        format: it.format,
        source: it.source,
      })
    }
  })

  return { results, unknowns }
}
