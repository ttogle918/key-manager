// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 브라우저 클라이언트 OCR (tesseract.js, Apache-2.0) — 스크린샷 → 라인 보존 텍스트.
 *
 * 모든 처리는 브라우저 안에서 일어난다(이미지·값이 기기를 떠나지 않음 — SPEC 프라이버시).
 * tesseract.js 는 무겁고(WASM+언어데이터) 이미지를 실제로 분석할 때만 필요하므로 **지연 로드**한다.
 * 여기서 뽑은 텍스트는 기존 `/analyze`(백엔드 Stage2)에 그대로 먹여 라벨-값 페어링을 재사용한다.
 */
import { reconstructText, type OcrWord } from './reconstruct'

/** tesseract.js recognize 결과에서 word 박스를 뽑는다(버전별 data.words / data.blocks 모두 대응). */
function extractWords(data: unknown): OcrWord[] {
  const d = data as {
    words?: OcrWord[]
    blocks?: Array<{
      paragraphs?: Array<{ lines?: Array<{ words?: OcrWord[] }> }>
    }>
  }
  if (Array.isArray(d.words) && d.words.length) return d.words
  const out: OcrWord[] = []
  for (const b of d.blocks || [])
    for (const p of b.paragraphs || [])
      for (const l of p.lines || [])
        for (const wd of l.words || []) out.push(wd)
  return out
}

export interface OcrProgress {
  /** 0~1 진행률(인식 단계). */
  progress: number
  status: string
}

/**
 * 이미지(dataURL/URL/Blob)에서 텍스트를 추출한다. 한글+영문 동시 인식.
 * @returns 라인 보존 텍스트(마스킹된 값은 `[마스킹됨]`, UI 잡음 제거) — Stage2 입력용.
 */
export async function runOcr(
  image: string | Blob,
  onProgress?: (p: OcrProgress) => void,
): Promise<string> {
  // 지연 로드: 이미지 분석 시점에만 무거운 엔진을 가져온다(초기 번들 경량 유지).
  const { createWorker } = await import('tesseract.js')
  // 로컬 벤더 자산 사용(scripts/vendor-tesseract.mjs) — 런타임 CDN 다운로드 없이 오프라인·재현 가능.
  const worker = await createWorker('eng+kor', 1, {
    workerPath: '/tesseract/worker.min.js',
    corePath: '/tesseract',
    langPath: '/tessdata',
    logger: onProgress
      ? (m: { progress?: number; status?: string }) => {
          if (m.status === 'recognizing text')
            onProgress({ progress: m.progress ?? 0, status: m.status })
        }
      : undefined,
  })
  try {
    // tesseract.js v6+ 는 기본적으로 word/block bbox 를 안 만든다 — 라벨-값 페어링에 필요하니 명시 요청.
    const { data } = await worker.recognize(image, {}, { blocks: true })
    return reconstructText(extractWords(data))
  } finally {
    await worker.terminate()
  }
}
