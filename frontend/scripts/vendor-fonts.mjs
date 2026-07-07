// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * 웹폰트 로컬 벤더링 — Pretendard(본문)·JetBrains Mono(값·키)를 빌드 시 public/fonts/ 로 받아둔다.
 *
 * 왜: KeyLens 는 **로컬 우선(local-first)** 도구다. 폰트를 Google Fonts·jsdelivr CDN 에서
 * 런타임 로드하면 앱을 열 때마다 외부 요청이 나가 "외부 서버 없음·오프라인" 원칙에 어긋난다.
 * → 폰트를 로컬에 두고 same-origin 으로 서빙한다(tesseract 자산 벤더링과 동일 패턴).
 *
 * 라이선스: 두 폰트 모두 **SIL Open Font License 1.1 (OFL-1.1, permissive)**. THIRD-PARTY-NOTICES 참조.
 * 받은 파일은 public/fonts/ 에만 두고 저장소엔 커밋하지 않는다(.gitignore).
 */
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const dst = join(root, 'public', 'fonts')

// (파일명, 다운로드 URL) — OFL-1.1
const FONTS = [
  [
    'PretendardVariable.woff2',
    'https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/woff2/PretendardVariable.woff2',
  ],
  [
    'JetBrainsMono-Regular.woff2',
    'https://cdn.jsdelivr.net/gh/JetBrains/JetBrainsMono@v2.304/fonts/webfonts/JetBrainsMono-Regular.woff2',
  ],
  [
    'JetBrainsMono-Medium.woff2',
    'https://cdn.jsdelivr.net/gh/JetBrains/JetBrainsMono@v2.304/fonts/webfonts/JetBrainsMono-Medium.woff2',
  ],
  [
    'JetBrainsMono-SemiBold.woff2',
    'https://cdn.jsdelivr.net/gh/JetBrains/JetBrainsMono@v2.304/fonts/webfonts/JetBrainsMono-SemiBold.woff2',
  ],
]

mkdirSync(dst, { recursive: true })
for (const [name, url] of FONTS) {
  const out = join(dst, name)
  if (existsSync(out)) {
    console.log(`[vendor-fonts] ${name} 이미 있음 — 건너뜀`)
    continue
  }
  console.log(`[vendor-fonts] ${name} 다운로드…`)
  const res = await fetch(url)
  if (!res.ok) {
    console.error(`[vendor-fonts] ${name} 다운로드 실패 (${res.status}) — 네트워크 확인`)
    process.exit(1)
  }
  writeFileSync(out, Buffer.from(await res.arrayBuffer()))
  console.log(`[vendor-fonts] ${name} → public/fonts/${name}`)
}
