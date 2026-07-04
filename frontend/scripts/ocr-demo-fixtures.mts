// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * DEMO-1 골든 OCR 픽스처 생성 (개발 전용).
 *
 * docs/demo/*.png 를 브라우저와 동일한 OCR 경로(tesseract.js + reconstruct)로 처리해
 * backend/tests/fixtures/demo/*.recon.txt 를 갱신한다. tesseract.js 버전/언어데이터가 바뀌면 다시 돌린다.
 *
 * 실행:  npm run vendor:ocr && node --experimental-strip-types scripts/ocr-demo-fixtures.mts
 * (vendor:ocr 로 public/tessdata 의 eng·kor 언어데이터가 준비돼 있어야 한다.)
 */
import { createWorker } from 'tesseract.js'
import { fileURLToPath } from 'node:url'
import { writeFileSync } from 'node:fs'
import { reconstructText, type OcrWord } from '../src/ocr/reconstruct.ts'

function extractWords(data: unknown): OcrWord[] {
  const d = data as {
    words?: OcrWord[]
    blocks?: Array<{ paragraphs?: Array<{ lines?: Array<{ words?: OcrWord[] }> }> }>
  }
  if (Array.isArray(d.words) && d.words.length) return d.words
  const out: OcrWord[] = []
  for (const b of d.blocks || [])
    for (const p of b.paragraphs || [])
      for (const l of p.lines || [])
        for (const w of l.words || []) out.push(w)
  return out
}

const NAMES = ['notion', 'kakao', 'gcp', 'openai']
const langPath = fileURLToPath(new URL('../public/tessdata', import.meta.url))
const worker = await createWorker('eng+kor', 1, { langPath })
for (const name of NAMES) {
  const img = fileURLToPath(new URL(`../../docs/demo/${name}.png`, import.meta.url))
  const { data } = await worker.recognize(img, {}, { blocks: true })
  const out = fileURLToPath(
    new URL(`../../backend/tests/fixtures/demo/${name}.recon.txt`, import.meta.url),
  )
  writeFileSync(out, reconstructText(extractWords(data)))
  console.log(`[ocr-demo] ${name} → backend/tests/fixtures/demo/${name}.recon.txt`)
}
await worker.terminate()
console.log('[ocr-demo] 완료.')
