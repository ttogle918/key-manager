// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 브라우저 클라이언트 OCR (tesseract.js, Apache-2.0) — 스크린샷 → 라인 보존 텍스트.
 *
 * 모든 처리는 브라우저 안에서 일어난다(이미지·값이 기기를 떠나지 않음 — SPEC 프라이버시).
 * tesseract.js 는 무겁고(WASM+언어데이터) 이미지를 실제로 분석할 때만 필요하므로 **지연 로드**한다.
 * 여기서 뽑은 텍스트는 기존 `/analyze`(백엔드 Stage2)에 그대로 먹여 라벨-값 페어링을 재사용한다.
 */
import { reconstruct, type OcrWord, type Reconstruction, type ValueToken } from './reconstruct'

/** 자격증명 값에 등장하는 문자만 허용 — 2차 정밀 인식에서 `0→@`·한글 등 charset 밖 오독을 막는다. */
const VALUE_WHITELIST =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-'
/** 한 번의 분석에서 값 영역 재인식 횟수 상한(비정상적으로 많은 후보 방어). */
const MAX_VALUE_PASSES = 16

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

/** worker 최소 인터페이스(setParameters + rectangle recognize). tesseract.js 타입에 의존하지 않기 위함. */
interface TessWorker {
  setParameters(p: Record<string, unknown>): Promise<unknown>
  recognize(
    image: string | Blob,
    opts?: { rectangle?: { left: number; top: number; width: number; height: number } },
  ): Promise<{ data: { text: string } }>
}

/**
 * 값 영역만 잘라 PSM(단일 라인) + charset whitelist 로 다시 읽어 정확도를 높인다(CORE-3 값 정밀화).
 * 전체 페이지 맥락에서 오독되던 값을, 값 영역만 단일 라인으로 보면 tesseract 가 더 잘 읽는다
 * (실측: 값 끝자리 `i`→`1` 오독이 교정됨). 크롭/분할이 어긋나 길이가 달라지면 2차를 버리고 1차를 유지한다.
 * rec 를 제자리 수정한다(text·flagged 의 값 문자열 치환).
 */
async function refineValues(
  worker: TessWorker,
  image: string | Blob,
  rec: Reconstruction,
  singleLinePsm: unknown,
): Promise<void> {
  const targets = rec.valueTokens.slice(0, MAX_VALUE_PASSES)
  if (!targets.length) return
  await worker.setParameters({
    tessedit_pageseg_mode: singleLinePsm,
    tessedit_char_whitelist: VALUE_WHITELIST,
  })
  for (const vt of targets) {
    const refined = await readValueRegion(worker, image, vt)
    // 길이 가드: 1차와 같은 길이일 때만 채택(어긋나면 크롭 실패로 보고 1차 유지 — 실측 kakao 퇴행 방지).
    if (refined && refined.length === vt.text.length && refined !== vt.text) {
      rec.text = rec.text.split(vt.text).join(refined)
      for (const f of rec.flagged) if (f.text === vt.text) f.text = refined
    }
  }
}

async function readValueRegion(
  worker: TessWorker,
  image: string | Blob,
  vt: ValueToken,
): Promise<string> {
  const pad = 6
  const rect = {
    left: Math.max(0, Math.round(vt.bbox.x0 - pad)),
    top: Math.max(0, Math.round(vt.bbox.y0 - pad)),
    width: Math.round(vt.bbox.x1 - vt.bbox.x0 + 2 * pad),
    height: Math.round(vt.bbox.y1 - vt.bbox.y0 + 2 * pad),
  }
  try {
    const { data } = await worker.recognize(image, { rectangle: rect })
    return data.text.trim().replace(/\s+/g, '')
  } catch {
    return '' // 재인식 실패는 무시하고 1차 유지
  }
}

/**
 * 이미지(dataURL/URL/Blob)에서 텍스트를 추출한다. 한글+영문 동시 인식.
 * @returns 라인 보존 텍스트 + 이어붙인 이음매(flagged) — 텍스트는 Stage2 입력, flagged 는 값 확인 표식용.
 */
export async function runOcr(
  image: string | Blob,
  onProgress?: (p: OcrProgress) => void,
): Promise<Reconstruction> {
  // 지연 로드: 이미지 분석 시점에만 무거운 엔진을 가져온다(초기 번들 경량 유지).
  const { createWorker, PSM } = await import('tesseract.js')
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
    // 1차: 전체 페이지. tesseract.js v6+ 는 기본적으로 word/block bbox 를 안 만들어 명시 요청(라벨-값 페어링용).
    const { data } = await worker.recognize(image, {}, { blocks: true })
    const rec = reconstruct(extractWords(data))
    // 2차: 값 영역만 PSM 단일 라인 + charset whitelist 로 정밀 재인식(값 정확도↑).
    await refineValues(worker as unknown as TessWorker, image, rec, PSM.SINGLE_LINE)
    return rec
  } finally {
    await worker.terminate()
  }
}
