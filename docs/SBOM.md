<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# SBOM — KeyLens 소프트웨어 구성 명세 (붙임1)

> 본 프로젝트(**MIT**)의 서드파티 구성요소 목록이다. 정책: **허용적(permissive) 라이선스만**
> (MIT / Apache-2.0 / BSD-2/3-Clause / ISC / 0BSD / Python-2.0). **카피레프트(GPL/AGPL/LGPL/MPL) 금지.**
> 판정 기준: **배포물에 포함되는 런타임 의존성** 중심. 빌드·테스트 전용(devDependencies)은 산출물에
> 실리지 않으므로 §4에 참고로 분리했다.
>
> 검증(2026-07-05): 백엔드 `pip-licenses`, 프론트 `license-checker --production` 전수 스캔 →
> **런타임 트리 카피레프트 0건**. (빌드 CSS 도구가 끌어오던 MPL-2.0 `lightningcss`는 tailwind 계열을
> devDependencies 로 재분류해 런타임 트리에서 제외 — 배포물에 애초에 실리지 않는 빌드타임 트랜스포머다.)

## 판정 요약

| 영역 | 패키지 수 | 카피레프트 | 판정 |
|---|---|---|---|
| 백엔드(Python, 런타임+테스트) | 20 | 0 | ✅ |
| 프론트(npm, production 트리) | ~64 | 0 | ✅ |

---

## 1. 백엔드 런타임 의존성 (Python)

### 1-1. 직접 의존성 (`backend/requirements.txt`)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 사용 목적 |
|---|---|---|---|---|---|
| 1 | fastapi | 0.115.6 | MIT | https://github.com/fastapi/fastapi | 로컬 API 서버 프레임워크 |
| 2 | uvicorn | 0.34.0 | BSD-3-Clause | https://github.com/encode/uvicorn | ASGI 서버(로컬 실행) |
| 3 | pydantic | 2.10.4 | MIT | https://github.com/pydantic/pydantic | 스키마 검증·직렬화 |
| 4 | PyYAML | 6.0.2 | MIT | https://github.com/yaml/pyyaml | 지식베이스 YAML 로드 |
| 5 | cryptography | 49.0.0 | Apache-2.0 OR BSD-3-Clause (BSD-3 선택) | https://github.com/pyca/cryptography | 금고 암호화(Argon2id + AES-256-GCM) |

### 1-2. 전이 의존성 (런타임)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 유입 |
|---|---|---|---|---|---|
| 6 | starlette | 0.41.3 | BSD-3-Clause | https://github.com/encode/starlette | ← fastapi |
| 7 | anyio | 4.14.1 | MIT | https://github.com/agronholm/anyio | ← starlette |
| 8 | idna | 3.18 | BSD-3-Clause | https://github.com/kjd/idna | ← anyio |
| 9 | typing_extensions | 4.16.0 | Python-2.0 (PSF) | https://github.com/python/typing_extensions | ← pydantic/fastapi/anyio |
| 10 | pydantic-core | 2.27.2 | MIT | https://github.com/pydantic/pydantic-core | ← pydantic |
| 11 | annotated-types | 0.7.0 | MIT | https://github.com/annotated-types/annotated-types | ← pydantic |
| 12 | click | 8.4.2 | BSD-3-Clause | https://github.com/pallets/click | ← uvicorn |
| 13 | h11 | 0.16.0 | MIT | https://github.com/python-hyper/h11 | ← uvicorn |
| 14 | colorama | 0.4.6 | BSD-3-Clause | https://github.com/tartley/colorama | ← click (Windows) |
| 15 | cffi | 2.0.0 | MIT | https://github.com/python-cffi/cffi | ← cryptography |
| 16 | pycparser | 3.0 | BSD-3-Clause | https://github.com/eliben/pycparser | ← cffi |

### 1-3. 테스트 전용 (`backend/requirements-dev.txt`, 배포물 아님)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 사용 목적 |
|---|---|---|---|---|---|
| 17 | pytest | 8.3.4 | MIT | https://github.com/pytest-dev/pytest | 테스트 러너 |
| 18 | packaging | 26.2 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging | ← pytest |
| 19 | iniconfig | 2.3.0 | MIT | https://github.com/pytest-dev/iniconfig | ← pytest |
| 20 | pluggy | 1.6.0 | MIT | https://github.com/pytest-dev/pluggy | ← pytest |

---

## 2. 프론트엔드 런타임 의존성 (npm, production)

### 2-1. 직접 의존성 (`frontend/package.json` dependencies)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 사용 목적 |
|---|---|---|---|---|---|
| 1 | react | 19.2.7 | MIT | https://github.com/facebook/react | UI 프레임워크 |
| 2 | react-dom | 19.2.7 | MIT | https://github.com/facebook/react | DOM 렌더러 |
| 3 | zustand | 5.0.14 | MIT | https://github.com/pmndrs/zustand | 상태 관리 |
| 4 | tesseract.js | 7.0.0 | Apache-2.0 | https://github.com/naptha/tesseract.js | 브라우저 OCR |
| 5 | @radix-ui/react-dialog | 1.1.18 | MIT | https://github.com/radix-ui/primitives | 접근성 다이얼로그 |
| 6 | @radix-ui/react-select | 2.3.2 | MIT | https://github.com/radix-ui/primitives | 접근성 셀렉트 |
| 7 | clsx | 2.1.1 | MIT | https://github.com/lukeed/clsx | 클래스 병합 |
| 8 | tailwind-merge | 3.6.0 | MIT | https://github.com/dcastil/tailwind-merge | Tailwind 클래스 충돌 해소 |
| 9 | lucide-react | 1.23.0 | ISC | https://github.com/lucide-icons/lucide | 아이콘 |

### 2-2. 주요 전이 의존성 (런타임)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 유입 |
|---|---|---|---|---|---|
| 10 | tesseract.js-core | 7.0.0 | Apache-2.0 | https://github.com/naptha/tesseract.js-core | ← tesseract.js |
| 11 | idb-keyval | 6.2.6 | Apache-2.0 | https://github.com/jakearchibald/idb-keyval | ← tesseract.js |
| 12 | wasm-feature-detect | 1.8.0 | Apache-2.0 | https://github.com/GoogleChromeLabs/wasm-feature-detect | ← tesseract.js |
| 13 | node-fetch | 2.7.0 | MIT | https://github.com/bitinn/node-fetch | ← tesseract.js |
| 14 | bmp-js | 0.1.0 | MIT | https://github.com/shaozilee/bmp-js | ← tesseract.js |
| 15 | is-url | 1.2.4 | MIT | https://github.com/segmentio/is-url | ← tesseract.js |
| 16 | zlibjs | 0.3.1 | MIT | https://github.com/imaya/zlib.js | ← tesseract.js |
| 17 | webidl-conversions | 3.0.1 | BSD-2-Clause | https://github.com/jsdom/webidl-conversions | ← tesseract.js |
| 18 | tslib | 2.8.1 | 0BSD | https://github.com/microsoft/tslib | ← radix-ui |

> 프론트 production 트리 전체(~64종)는 MIT/Apache-2.0/ISC/0BSD/BSD-2로만 구성. 위 표는 대표 항목이며
> 전체 목록은 `frontend/`에서 `npx license-checker --production --json`으로 재생성한다.

---

## 3. 참고 자산 (AI 모델 / 데이터)

| 자산 | 버전 | 라이선스 | 출처 | 사용 목적 |
|---|---|---|---|---|
| Tesseract 학습 데이터 (eng·kor `.traineddata`) | tessdata_fast | Apache-2.0 | https://github.com/tesseract-ocr/tessdata_fast | OCR 언어 모델(로컬 벤더링) |
| tesseract.js WASM core | 7.0.0 | Apache-2.0 | https://github.com/naptha/tesseract.js-core | OCR 추론 엔진(WASM) |

> ⚠️ 붙임2(AI 모델 활용 명세서)와 연동: OCR 엔진은 **외부 모델 그대로 활용(유형1)**, 파인튜닝 없음. 상세는 OSS-4.

---

## 4. 개발·빌드 전용 (배포물에 미포함 — 참고)

산출물(`dist/`, 백엔드 실행)에는 실리지 않는 도구들. 카피레프트 없음.

- **프론트(devDependencies)**: vite, vitest, oxlint, typescript, @vitejs/plugin-react, @types/*,
  **tailwindcss·@tailwindcss/vite**(빌드타임 CSS — 이들이 끌어오는 `lightningcss`는 MPL-2.0이나
  컴파일된 CSS만 배포되어 산출물에 미포함). dev 트리 라이선스: MIT/Apache-2.0/ISC.
- **백엔드(dev)**: 위 §1-3 참고.
- **일회성 스캔 도구**(설치 후 제거): pip-licenses(MIT), license-checker(BSD-3-Clause).

---

## 재생성 방법

```bash
# 백엔드
cd backend && ./.venv/Scripts/python.exe -m pip install -q pip-licenses
./.venv/Scripts/python.exe -m piplicenses --format=markdown --with-urls --order=license
# 프론트 (배포물 판정 기준)
cd frontend && npx --yes license-checker --production --summary
```
