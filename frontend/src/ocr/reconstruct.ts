// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * OCR 단어 박스 → 라인 보존 텍스트 재구성 (CORE-3의 난이도 핵심: 라벨-값 공간 페어링).
 *
 * 엔진 독립적인 순수 로직 — 입력은 tesseract.js 의 word 출력과 같은 모양이면 무엇이든 된다.
 * 목적: 값과 라벨의 "위치 관계"(같은 행 / 바로 위 행)를 텍스트 줄 구조로 보존해,
 * 백엔드 Stage2(`classify_context`)의 라벨-값 페어링에 그대로 먹일 수 있게 만든다.
 * OCR 엔진(tesseract.js)은 이 함수에 박스를 공급하는 입력 경로일 뿐.
 */

/** 픽셀 bbox. */
export interface BBox {
  x0: number
  y0: number
  x1: number
  y1: number
}

/** tesseract.js word 와 호환되는 최소 형태. bbox 좌표는 픽셀. */
export interface OcrWord {
  text: string
  bbox: BBox
}

/** 마스킹 문자(가려진 값)로 흔히 쓰이는 글리프 — 진짜 값이 아니므로 값 후보에서 제외한다. */
const MASK_GLYPHS = /[•·●∙・*※‧⋅]/
/** 콘솔 UI 잡음(복사/표시/재발급 버튼 등) — 라벨/값이 아니다. */
const NOISE_WORDS = new Set([
  'copy',
  'copied',
  '복사',
  '복사됨',
  'show',
  'hide',
  '표시',
  '숨기기',
  'reveal',
  'regenerate',
  '재발급',
  'refresh',
  'reset',
  'edit',
  'delete',
  '삭제',
])

/** 토큰이 마스킹된 값인지: 마스킹 글리프가 2개 이상 연속하거나 토큰의 상당 부분이면 마스킹으로 본다. */
export function isMasked(token: string): boolean {
  const masks = (token.match(new RegExp(MASK_GLYPHS, 'g')) || []).length
  if (masks === 0) return false
  // secret_•••• 처럼 접두어 + 가림, 또는 •••• 통짜 가림 모두 포착.
  return masks >= 2 || masks / token.length >= 0.4
}

/** 잡음 토큰(빈 문자열·UI 버튼)인지. */
function isNoise(token: string): boolean {
  const t = token.trim()
  if (!t) return true
  return NOISE_WORDS.has(t.toLowerCase())
}

/**
 * 자격증명 값처럼 보이는 토큰인지 — 값 전용 정밀 재인식(2차 OCR) 대상 선별용.
 * 공백 없는 긴 영숫자(+구분자) 토큰, 또는 16자 이상 hex. 라벨은 보통 짧거나 공백을 포함해 걸러진다.
 */
export function looksLikeValue(token: string): boolean {
  return /^[A-Za-z0-9._-]{20,}$/.test(token) || /^[0-9a-fA-F]{16,}$/.test(token)
}

const cy = (w: OcrWord) => (w.bbox.y0 + w.bbox.y1) / 2
const height = (w: OcrWord) => Math.max(1, w.bbox.y1 - w.bbox.y0)
/** 글자당 평균 너비(px) 추정 — 토큰 사이 간격이 '진짜 공백'인지 판단하는 기준. */
const charWidth = (w: OcrWord) =>
  Math.max(1, (w.bbox.x1 - w.bbox.x0) / Math.max(1, w.text.length))

/**
 * 단어 박스를 행(row)으로 묶는다. 세로 중심(cy)이 현재 행 평균과 단어 높이의 절반 이내면 같은 행.
 * 반환: 위→아래 정렬된 행들, 각 행은 좌→우 정렬된 단어 목록.
 */
export function groupRows(words: OcrWord[]): OcrWord[][] {
  const sorted = [...words].sort((a, b) => cy(a) - cy(b))
  const rows: { center: number; words: OcrWord[] }[] = []
  for (const w of sorted) {
    const tol = height(w) * 0.6
    const row = rows.find((r) => Math.abs(r.center - cy(w)) <= tol)
    if (row) {
      row.words.push(w)
      // 러닝 평균으로 중심 갱신(행이 기울어도 안정적).
      row.center = (row.center * (row.words.length - 1) + cy(w)) / row.words.length
    } else {
      rows.push({ center: cy(w), words: [w] })
    }
  }
  return rows.map((r) => r.words.sort((a, b) => a.bbox.x0 - b.bbox.x0))
}

/** OCR 이 촘촘한 간격 때문에 이어붙인 토큰과, 그 이음매(불확실) 글자 위치. */
export interface FlaggedToken {
  /** 이어붙여 만든 최종 토큰 문자열(= 분류에 쓰인 값과 동일). */
  text: string
  /** 이음매 글자 인덱스 목록(그 지점 앞뒤가 OCR 상 불확실 — 사용자 확인 권장). */
  marks: number[]
}

/** 값처럼 보이는 토큰과 그 화면 영역(2차 정밀 재인식 대상). */
export interface ValueToken {
  /** 1차 OCR 로 읽은 값 토큰(= 분류에 쓰인 값). */
  text: string
  /** 구성 단어들의 합집합 bbox — 이 영역만 잘라 PSM/whitelist 로 다시 읽는다. */
  bbox: BBox
}

export interface Reconstruction {
  /** 라인 보존 텍스트(백엔드 분류 입력). */
  text: string
  /** 간격 결합으로 만들어진 토큰들(사용자에게 "여기 확인" 표식용). */
  flagged: FlaggedToken[]
  /** 값처럼 보이는 토큰들 — ocr.ts 가 이 영역만 정밀 재인식해 정확도를 높인다. */
  valueTokens: ValueToken[]
}

function unionBBox(ws: OcrWord[]): BBox {
  return {
    x0: Math.min(...ws.map((w) => w.bbox.x0)),
    y0: Math.min(...ws.map((w) => w.bbox.y0)),
    x1: Math.max(...ws.map((w) => w.bbox.x1)),
    y1: Math.max(...ws.map((w) => w.bbox.y1)),
  }
}

/**
 * 단어 박스들을 라인 보존 텍스트로 재구성한다.
 * - 행 그룹핑으로 같은 줄/윗줄 관계를 보존(→ Stage2 라벨 페어링).
 * - 마스킹된 값은 리터럴 `[마스킹됨]` 자리표시자로 치환(가짜 값 생성 금지, SPEC/CORE-3 AC).
 * - UI 잡음 단어는 제거.
 * - **간격 인식 결합**: OCR 이 `key.value` 같은 한 토큰을 구두점에서 둘로 쪼갠 경우(간격이
 *   글자폭보다 훨씬 작음) 공백 없이 붙인다 — 실제 값이 끊기지 않게(실측: `6789. Dumm` → `6789.Dumm`).
 *   이렇게 이어붙인 이음매는 OCR 상 불확실하므로 위치를 `flagged`로 남겨 UI가 표시하게 한다.
 */
export function reconstruct(words: OcrWord[]): Reconstruction {
  const rows = groupRows(words)
  const lines: string[] = []
  const flagged: FlaggedToken[] = []
  const valueTokens: ValueToken[] = []

  for (const row of rows) {
    const kept = row.filter((w) => !isNoise(w.text))
    const segments: string[] = [] // 공백으로 나뉜 논리 토큰들
    let seg = ''
    let segMarks: number[] = []
    let segWords: OcrWord[] = [] // 현재 세그먼트를 이루는 원본 단어들(값 영역 bbox 계산용)
    const flush = () => {
      if (seg) {
        segments.push(seg)
        if (segMarks.length) flagged.push({ text: seg, marks: segMarks })
        if (looksLikeValue(seg) && segWords.length) {
          valueTokens.push({ text: seg, bbox: unionBBox(segWords) })
        }
      }
      seg = ''
      segMarks = []
      segWords = []
    }
    for (let i = 0; i < kept.length; i++) {
      const w = kept[i]
      const token = isMasked(w.text) ? '[마스킹됨]' : w.text
      if (i === 0) {
        seg = token
        segWords = [w]
        continue
      }
      const prev = kept[i - 1]
      const gap = w.bbox.x0 - prev.bbox.x1
      // 정상 단어 공백은 글자폭의 ~1배(모노스페이스). 반 글자폭 미만이면 한 토큰이 쪼개진 것 → 붙임.
      // (실측 보정: 고해상도 스크린샷에서 구두점 분리 간격 ≈ 5px, 글자폭 ≈ 13px.)
      const tight = gap < 0.5 * Math.min(charWidth(prev), charWidth(w))
      if (tight) {
        segMarks.push(seg.length) // 이음매 = 다음 토큰이 시작되는 글자 위치
        seg += token
        segWords.push(w)
      } else {
        flush()
        seg = token
        segWords = [w]
      }
    }
    flush()
    const line = segments.join(' ').trim()
    if (line) lines.push(line)
  }
  return { text: lines.join('\n'), flagged, valueTokens }
}

/** 텍스트만 필요할 때(백엔드 입력·회귀 픽스처). */
export function reconstructText(words: OcrWord[]): string {
  return reconstruct(words).text
}
