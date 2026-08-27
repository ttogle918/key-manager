// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * simple-icons(CC0-1.0 — 저작권은 포기되지만 상표권은 각 브랜드사 소유, THIRD-PARTY-NOTICES.md
 * 참고)에서 KeyLens가 쓰는 6개 서비스 로고만 뽑아 src/assets/logos/ 에 커밋 대상 정적 파일로
 * 복사한다. 런타임 코드는 simple-icons를 import하지 않는다(devDependency 전용) — 결과 SVG
 * 파일 6개(수 KB)만 저장소에 커밋하고, tesseract 모델처럼 매 빌드마다 다시 뽑을 필요는 없다.
 * 새 서비스 로고가 필요해지면 LOGOS에 한 줄 추가 후 수동 실행: npm run vendor:logos
 *
 * OpenAI·Slack·AWS는 simple-icons에 아이콘 자체가 없다(브랜드 요청으로 제거됨 —
 * node_modules/simple-icons/DISCLAIMER.md의 "Removal of Brands" 참고). 이 세 서비스는
 * KeyLens에서 로고 없이 기존 컬러 이니셜 타일 폴백을 쓴다(services.ts, 자동).
 */
import { cpSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const src = join(root, 'node_modules', 'simple-icons', 'icons')
const dst = join(root, 'src', 'assets', 'logos')

// KeyLens 서비스 id(backend/knowledge/*.yaml 의 `service:`) → simple-icons slug.
// openai/aws/slack은 simple-icons에 없어(브랜드 요청 제거) 의도적으로 뺐다 — 폴백 타일 사용.
const LOGOS = {
  notion: 'notion',
  kakao: 'kakao',
  gcp: 'googlecloud',
  ollama: 'ollama',
  github: 'github',
  stripe: 'stripe',
}

if (!existsSync(src)) {
  console.error('[vendor-logos] node_modules/simple-icons 없음 — npm install 먼저')
  process.exit(1)
}
mkdirSync(dst, { recursive: true })
for (const [id, slug] of Object.entries(LOGOS)) {
  const from = join(src, `${slug}.svg`)
  if (!existsSync(from)) {
    console.error(`[vendor-logos] icons/${slug}.svg 없음 — simple-icons 버전이 바뀌었을 수 있음`)
    process.exit(1)
  }
  cpSync(from, join(dst, `${id}.svg`))
}
console.log(`[vendor-logos] ${Object.keys(LOGOS).length}개 로고 → src/assets/logos/`)
