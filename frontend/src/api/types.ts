// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/** 백엔드 `/analyze` 응답 계약 (backend/app/models.py 와 일치). */

export type ApiConfidence = 'high' | 'medium' | 'unknown'

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
