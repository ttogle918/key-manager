// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * tesseract.js 자산을 로컬로 벤더링한다 (재현성 — 런타임 CDN 다운로드 제거).
 *
 * - core WASM + worker: node_modules 에서 public/tesseract/ 로 복사 (package-lock 으로 결정적).
 * - 언어 데이터(eng·kor traineddata, Apache-2.0): tessdata_fast 에서 받아 gzip 후 public/tessdata/ 에 둔다.
 *
 * predev/prebuild 훅으로 자동 실행. 이미 있으면 건너뛴다(오프라인 재빌드 가능).
 * 출처·라이선스: THIRD-PARTY-NOTICES.md 참고.
 */
import { cpSync, existsSync, mkdirSync, readdirSync, writeFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const coreSrc = join(root, 'node_modules', 'tesseract.js-core')
const workerSrc = join(root, 'node_modules', 'tesseract.js', 'dist', 'worker.min.js')
const coreDst = join(root, 'public', 'tesseract')
const dataDst = join(root, 'public', 'tessdata')

// tessdata_fast(Apache-2.0). tesseract.js 는 기본적으로 <langPath>/<lang>.traineddata.gz 를 받아 gunzip 한다.
const LANGS = ['eng', 'kor']
const DATA_BASE = 'https://github.com/tesseract-ocr/tessdata_fast/raw/main'

function vendorCore() {
  if (!existsSync(coreSrc)) {
    console.error('[vendor-tesseract] node_modules/tesseract.js-core 없음 — npm install 먼저')
    process.exit(1)
  }
  mkdirSync(coreDst, { recursive: true })
  // core wasm 변형 전부 복사(런타임이 브라우저 SIMD 지원에 맞는 것을 고른다).
  for (const f of readdirSync(coreSrc)) {
    if (f.endsWith('.wasm') || f.endsWith('.wasm.js') || f.endsWith('.js'))
      cpSync(join(coreSrc, f), join(coreDst, f))
  }
  cpSync(workerSrc, join(coreDst, 'worker.min.js'))
  console.log(`[vendor-tesseract] core+worker → public/tesseract/`)
}

async function vendorLangs() {
  mkdirSync(dataDst, { recursive: true })
  for (const lang of LANGS) {
    const out = join(dataDst, `${lang}.traineddata.gz`)
    if (existsSync(out)) {
      console.log(`[vendor-tesseract] ${lang} 이미 있음 — 건너뜀`)
      continue
    }
    const url = `${DATA_BASE}/${lang}.traineddata`
    console.log(`[vendor-tesseract] ${lang} 다운로드…`)
    const res = await fetch(url)
    if (!res.ok) {
      console.error(`[vendor-tesseract] ${lang} 다운로드 실패 (${res.status}) — 네트워크 확인`)
      process.exit(1)
    }
    const buf = Buffer.from(await res.arrayBuffer())
    writeFileSync(out, gzipSync(buf)) // tesseract.js 가 .gz 를 gunzip 한다.
    console.log(`[vendor-tesseract] ${lang} → public/tessdata/${lang}.traineddata.gz`)
  }
}

vendorCore()
await vendorLangs()
console.log('[vendor-tesseract] 완료.')
