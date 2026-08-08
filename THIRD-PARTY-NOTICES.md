<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# THIRD-PARTY NOTICES

이 프로젝트(MIT)는 다음 서드파티 구성요소를 사용합니다. 각 구성요소는 해당 라이선스 조건을 따릅니다.
모든 항목은 허용적(permissive) 라이선스이며, 카피레프트(GPL/AGPL/LGPL/MPL)는 포함하지 않습니다.

## 브라우저 OCR (frontend, CORE-3)

### tesseract.js
- 버전: 7.0.0
- 라이선스: Apache-2.0
- 출처: https://github.com/naptha/tesseract.js
- 비고: 런타임 전이 의존성 전부 permissive — tesseract.js-core·idb-keyval·wasm-feature-detect(Apache-2.0);
  bmp-js·is-url·node-fetch·opencollective-postinstall·regenerator-runtime·whatwg-url·tr46·zlibjs(MIT);
  webidl-conversions(BSD-2-Clause).

### tesseract.js-core (WASM 엔진)
- 버전: 7.0.0
- 라이선스: Apache-2.0
- 출처: https://github.com/naptha/tesseract.js-core

### Tesseract 학습 데이터 (traineddata)
- 파일: eng.traineddata, kor.traineddata
- 라이선스: Apache-2.0
- 출처: https://github.com/tesseract-ocr/tessdata_fast
  (고정밀이 필요하면 https://github.com/tesseract-ocr/tessdata_best, 동일 Apache-2.0)
- 비고: 재현성을 위해 위 저장소의 파일을 `frontend/scripts/vendor-tesseract.mjs`가
  `frontend/public/tessdata/`에 로컬 번들한다. 런타임 CDN 다운로드는 사용하지 않는다.
  (core WASM·worker 역시 node_modules에서 `frontend/public/tesseract/`로 로컬 복사.)

## 암호화 저장소 (backend, VAULT-1)

### cryptography
- 버전: 49.0.0
- 라이선스: Apache-2.0 OR BSD-3-Clause (듀얼 — 본 프로젝트는 **BSD-3-Clause를 선택 적용**)
- 출처: https://pypi.org/project/cryptography/49.0.0/ · https://github.com/pyca/cryptography
- 용도: Argon2id 키 유도(KDF) + AES-256-GCM 항목별 암호화. 코드 복사 없이 공개 API만 호출
  (`hazmat.primitives.kdf.argon2.Argon2id`, `hazmat.primitives.ciphers.aead.AESGCM`).
- 전이 의존성: cffi 2.0.0 (MIT), pycparser 3.0 (BSD-3-Clause). certifi/MPL/카피레프트 없음.

## 프론트엔드 런타임 (React SPA — 배포 번들 포함)

| 패키지 | 버전 | 라이선스 | 출처 |
|---|---|---|---|
| react · react-dom | 19.2.7 | MIT | https://github.com/facebook/react |
| @radix-ui/react-dialog · react-select | 1.1.18 · 2.3.2 | MIT | https://github.com/radix-ui/primitives |
| zustand | 5.0.14 | MIT | https://github.com/pmndrs/zustand |
| clsx | 2.1.1 | MIT | https://github.com/lukeed/clsx |
| tailwind-merge | 3.6.0 | MIT | https://github.com/dcastil/tailwind-merge |
| tailwindcss | 4.3.2 | MIT | https://github.com/tailwindlabs/tailwindcss (생성 CSS가 배포물에 포함) |

## 웹폰트 (로컬 벤더링 — 배포 번들 포함, CDN 미사용)

| 폰트 | 버전 | 라이선스 | 출처 |
|---|---|---|---|
| Pretendard (Variable) | 1.3.9 | OFL-1.1 | https://github.com/orioncactus/pretendard |
| JetBrains Mono | 2.304 | OFL-1.1 | https://github.com/JetBrains/JetBrainsMono |

- 두 폰트 모두 **SIL Open Font License 1.1 (permissive)** — 임베드·재배포 허용(폰트 단독 판매 금지·예약 명칭 유지).
- **local-first**: Google Fonts·jsdelivr CDN 런타임 로드를 없애고, `frontend/scripts/vendor-fonts.mjs`가 빌드 시
  `public/fonts/`로 받아 same-origin 서빙한다(외부 요청 0). 폰트 파일은 저장소에 커밋하지 않는다(.gitignore).
> OFL 전문: https://openfontlicense.org/

## 백엔드 런타임 (FastAPI 로컬 서버)

| 패키지 | 버전 | 라이선스 | 출처 |
|---|---|---|---|
| fastapi | 0.139.0 | MIT | https://github.com/fastapi/fastapi |
| starlette | 1.3.1 | BSD-3-Clause | https://github.com/encode/starlette |
| uvicorn | 0.34.0 | BSD-3-Clause | https://github.com/encode/uvicorn |
| pydantic | 2.10.4 | MIT | https://github.com/pydantic/pydantic |
| PyYAML | 6.0.2 | MIT | https://github.com/yaml/pyyaml |

> 전체 의존성(전이 포함)·SBOM 6컬럼 표는 [docs/SBOM.md](./docs/SBOM.md) 참고. 런타임 트리 카피레프트 0건(2026-07-05 스캔).

## 데스크톱 앱 (`desktop/`, 선택 — 웹 배포물엔 미포함)

| 구성요소 | 버전 | 라이선스 | 출처·비고 |
|---|---|---|---|
| pywebview | 6.2.1 | BSD-3-Clause | https://github.com/r0x0r/pywebview — 네이티브 창. 전이 pythonnet·clr-loader·bottle·proxy_tools(전부 MIT) |
| plyer | 2.1.0 | MIT | https://github.com/kivy/plyer — OS 네이티브 토스트 알림(RUNTIME-1). 전이 의존성 없음, Windows 경로는 순수 stdlib `ctypes`만 사용 |
| cx_Freeze | 8.x | PSF 계열 permissive | https://cx-freeze.readthedocs.io/en/latest/license.html — **빌드 도구**(실행 파일에 도구 코드 미포함) |

- 실행 파일 패키징 기본 패키저는 **cx_Freeze(permissive)**. 대안 Nuitka(Apache-2.0).
- **PyInstaller(GPL-2.0 + 예외)** 도 사용 가능하다 — 예외 조항상 **생성된 실행 파일은 GPL에 묶이지 않으며**
  원하는 라이선스(본 프로젝트 MIT)로 배포할 수 있다(부트로더 미수정 시). 근거: https://pyinstaller.org/en/stable/license.html
- WebView2 런타임은 Windows 기본 포함 OS 구성요소로 파이썬 의존성이 아니다.

## 키 포맷 정규식 (지식베이스 `backend/knowledge/*.yaml`)

- 각 서비스 키의 `value_regex`(접두어·길이·문자셋)는 **해당 서비스의 공식 문서/변경로그를 근거로 직접 작성**했다.
  코드·패턴을 그대로 복사하지 않았으며, 특히 **TruffleHog(AGPL-3.0)의 탐지 패턴은 참조하지 않았다**(CLAUDE.md 규칙).
- 근거로 삼은 공식 문서: GitHub 인증 토큰 포맷 변경로그(2021), AWS Access Key ID 포맷 문서, Slack Tokens 문서,
  Stripe API keys 문서. 포맷은 공개적으로 널리 문서화된 사실(접두어 등)이다.
- 참고로 Gitleaks(MIT), 각 벤더의 secret-scanning 문서 등 permissive/공개 출처와 교차 확인했으며, 도입한 코드는 없다.

## 발급 도움말 데이터 (지식베이스 GUIDE-1/2 필드)

- KB의 `role`·`issue_url`·`docs_url`·`console_url`·`steps`·`prereq`·`exposure`·`security_tip`·`disambiguation`
  값은 **각 서비스의 공식 문서·개발자 콘솔을 근거로 정리한 사실 정보**다(발급 위치·키 역할·보안 등급 등).
  각 `docs_url` 이 그 출처 링크이며, 벤더의 저작물 텍스트를 그대로 복제하지 않고 요약·재작성했다.
- 조사 출처 예: Notion Developers, Kakao Developers, Google Cloud 문서, AWS IAM 문서, OpenAI/Slack/Stripe/GitHub 공식 문서.

> 전문: https://www.apache.org/licenses/LICENSE-2.0
