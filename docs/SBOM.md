<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# SBOM — KeyLens 소프트웨어 구성 명세 (붙임1)

> 본 프로젝트(**MIT**)의 서드파티 구성요소 목록이다. 정책: **허용적(permissive) 라이선스만**
> (MIT / Apache-2.0 / BSD-2/3-Clause / ISC / 0BSD / Python-2.0). **강한 카피레프트(GPL/AGPL) 금지,
> 약한 카피레프트(LGPL/MPL)는 패키지를 수정 없이 그대로 의존할 때만 조건부 허용**(CLAUDE.md 규칙과 동일 —
> 실제 조건부 허용 사례는 §1-1b의 MPL-2.0 2건).
> 판정 기준: **배포물에 포함되는 런타임 의존성** 중심. 빌드·테스트 전용(devDependencies)은 산출물에
> 실리지 않으므로 §4에 참고로 분리했다.
>
> 검증(2026-08-27, CORE-3 백엔드 OCR·MUI 도입 반영): 백엔드 `pip-licenses`, 프론트
> `license-checker --production` 전수 스캔 → **강한 카피레프트(GPL/AGPL) 0건**. 단, 스크린샷 OCR을
> 백엔드 RapidOCR로 전환하며 유입된 전이 의존성 중 **약한 카피레프트(MPL-2.0) 2건**(`tqdm`·`certifi`)이
> 있다 — 둘 다 **수정 없이 그대로 사용**해 CLAUDE.md 조건부 허용 기준을 충족하며, 안전 근거는
> [THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md#스크린샷-ocr-backend-core-3--한국어-라벨-인식-정확도-개선)에
> 상세 기록했다. (빌드 CSS 도구가 끌어오던 MPL-2.0 `lightningcss`는 tailwind 계열을 devDependencies 로
> 재분류해 런타임 트리에서 제외 — 배포물에 애초에 실리지 않는 빌드타임 트랜스포머다.)

## 판정 요약

| 영역 | 패키지 수(직접) | 강한 카피레프트 | 약한 카피레프트(조건부 허용) | 판정 |
|---|---|---|---|---|
| 백엔드(Python, 런타임) | 9 (+ RapidOCR 전이 트리) | 0 | 2건(tqdm·certifi, MPL-2.0 — 미수정 사용) | ✅ |
| 프론트(npm, production 트리) | 13 | 0 | 0 | ✅ |

> 정확한 전체(전이 포함) 개수는 스택 변경이 잦아 고정 숫자 대신 "재생성 방법"(하단)으로 그때그때
> 재산출한다. 위 표는 직접 의존성 기준.

---

## 1. 백엔드 런타임 의존성 (Python)

### 1-1. 직접 의존성 (`backend/requirements.txt`)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 사용 목적 |
|---|---|---|---|---|---|
| 1 | fastapi | 0.139.0 | MIT | https://github.com/fastapi/fastapi | 로컬 API 서버 프레임워크 |
| 2 | starlette | 1.3.1 | BSD-3-Clause | https://github.com/encode/starlette | ASGI 툴킷(fastapi 기반) — CVE 패치본 명시 고정(§5) |
| 3 | uvicorn | 0.34.0 | BSD-3-Clause | https://github.com/encode/uvicorn | ASGI 서버(로컬 실행) |
| 4 | pydantic | 2.10.4 | MIT | https://github.com/pydantic/pydantic | 스키마 검증·직렬화 |
| 5 | PyYAML | 6.0.2 | MIT | https://github.com/yaml/pyyaml | 지식베이스 YAML 로드 |
| 6 | cryptography | 50.0.1 | Apache-2.0 OR BSD-3-Clause (BSD-3 선택) | https://github.com/pyca/cryptography | 금고 암호화(Argon2id + AES-256-GCM) — PYSEC-2026-3552 패치본 |
| 7 | python-multipart | 0.0.32 | Apache-2.0 | https://github.com/Kludex/python-multipart | FastAPI `UploadFile`(스크린샷 이미지 업로드, CORE-3 백엔드 OCR)에 필요 |
| 8 | rapidocr | 3.9.2 | Apache-2.0 | https://github.com/RapidAI/RapidOCR | 스크린샷 OCR(백엔드) — PP-OCR(det/cls/rec) ONNX 추론 래퍼 |
| 9 | onnxruntime | 1.29.0 | MIT | https://github.com/microsoft/onnxruntime | rapidocr 추론 엔진 |

### 1-1b. `rapidocr` 전이 의존성 중 약한 카피레프트(조건부 허용)

CLAUDE.md 규칙에 따라 별도 기록. 둘 다 **수정 없이 그대로 사용** — 안전 근거는
[THIRD-PARTY-NOTICES.md](../THIRD-PARTY-NOTICES.md) 참고.

| # | 라이브러리명 | 라이선스 | 유입 경로 | 안전 근거 요약 |
|---|---|---|---|---|
| ※1 | tqdm | MPL-2.0(파일 단위 카피레프트) | ← rapidocr 필수 전이 의존성 | 소스 미수정, pip 의존성으로만 사용 → 이 프로젝트(MIT) 코드로 비전염 |
| ※2 | certifi | MPL-2.0(파일 단위 카피레프트) | ← rapidocr → requests 전이 의존성 | CA 인증서 데이터 패키지, 소스 미수정 → 비전염(cryptography 자체는 certifi를 끌어오지 않음) |

> `opencv-python`(rapidocr 필수 전이 의존성)도 Windows 휠에 LGPL-2.1 `FFmpeg`가 동봉되나, cv2 본체와
> **분리된 재교체 가능 플러그인 DLL**로 동적 로드돼(`opencv_videoio_ffmpeg500_64.dll`) LGPL 재링크
> 요건을 충족한다 — 상세는 THIRD-PARTY-NOTICES.md. pip-licenses는 이 패키지를 Apache-2.0으로만
> 인식하므로 위 표(pip-licenses 결과 기준)에는 별도 행으로 잡히지 않는다.

### 1-2. 전이 의존성 (런타임, fastapi/uvicorn/cryptography 계열만 — rapidocr 전이 트리는 위 1-1b·THIRD-PARTY-NOTICES.md 참고)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 유입 |
|---|---|---|---|---|---|
| 7 | anyio | 4.14.1 | MIT | https://github.com/agronholm/anyio | ← starlette |
| 8 | idna | 3.18 | BSD-3-Clause | https://github.com/kjd/idna | ← anyio |
| 9 | typing_extensions | 4.16.0 | Python-2.0 (PSF) | https://github.com/python/typing_extensions | ← pydantic/fastapi/anyio |
| 10 | typing-inspection | 0.4.2 | MIT | https://github.com/pydantic/typing-inspection | ← pydantic/fastapi |
| 11 | annotated-doc | 0.0.4 | MIT | https://github.com/tiangolo/annotated-doc | ← fastapi |
| 12 | pydantic-core | 2.27.2 | MIT | https://github.com/pydantic/pydantic-core | ← pydantic |
| 13 | annotated-types | 0.7.0 | MIT | https://github.com/annotated-types/annotated-types | ← pydantic |
| 14 | click | 8.4.2 | BSD-3-Clause | https://github.com/pallets/click | ← uvicorn |
| 15 | h11 | 0.16.0 | MIT | https://github.com/python-hyper/h11 | ← uvicorn |
| 16 | colorama | 0.4.6 | BSD-3-Clause | https://github.com/tartley/colorama | ← click (Windows) |
| 17 | cffi | 2.0.0 | MIT | https://github.com/python-cffi/cffi | ← cryptography |
| 18 | pycparser | 3.0 | BSD-3-Clause | https://github.com/eliben/pycparser | ← cffi |

### 1-3. 테스트 전용 (`backend/requirements-dev.txt`, 배포물 아님)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 사용 목적 |
|---|---|---|---|---|---|
| 19 | pytest | 9.0.3 | MIT | https://github.com/pytest-dev/pytest | 테스트 러너 |
| 20 | packaging | 26.2 | Apache-2.0 OR BSD-2-Clause | https://github.com/pypa/packaging | ← pytest |
| 21 | iniconfig | 2.3.0 | MIT | https://github.com/pytest-dev/iniconfig | ← pytest |
| 22 | pluggy | 1.6.0 | MIT | https://github.com/pytest-dev/pluggy | ← pytest |

---

## 2. 프론트엔드 런타임 의존성 (npm, production)

### 2-1. 직접 의존성 (`frontend/package.json` dependencies)

| # | 라이브러리명 | 버전 | 라이선스 | 공식 저장소 URL | 사용 목적 |
|---|---|---|---|---|---|
| 1 | react | 19.2.7 | MIT | https://github.com/facebook/react | UI 프레임워크 |
| 2 | react-dom | 19.2.7 | MIT | https://github.com/facebook/react | DOM 렌더러 |
| 3 | zustand | 5.0.14 | MIT | https://github.com/pmndrs/zustand | 상태 관리 |
| 4 | tesseract.js | 7.0.0 | Apache-2.0 | https://github.com/naptha/tesseract.js | ⚠️ **레거시** — CORE-3에서 백엔드 RapidOCR로 대체, 현재 분석 흐름에서 미호출(재구성 로직 유닛테스트만 참조) |
| 5 | @radix-ui/react-dialog | 1.1.18 | MIT | https://github.com/radix-ui/primitives | 접근성 다이얼로그 |
| 6 | @radix-ui/react-select | 2.3.2 | MIT | https://github.com/radix-ui/primitives | 접근성 셀렉트 |
| 7 | clsx | 2.1.1 | MIT | https://github.com/lukeed/clsx | 클래스 병합 |
| 8 | tailwind-merge | 3.6.0 | MIT | https://github.com/dcastil/tailwind-merge | Tailwind 클래스 충돌 해소 |
| 9 | @mui/material | 9.3.1 | MIT | https://github.com/mui/material-ui | 분석 결과 요약 DataGrid UI(`frontend/src/mui/theme.ts`) |
| 10 | @mui/x-data-grid | 9.12.0 | MIT(Community 등급) | https://github.com/mui/mui-x | 결과 목록 표(`ResultsGrid.tsx`) — ⚠️ Pro/Premium 유료 등급 미사용, Community만 사용 |
| 11 | @emotion/react | 11.14.0 | MIT | https://github.com/emotion-js/emotion | MUI 스타일링 엔진(전이 의존성) |
| 12 | @emotion/styled | 11.14.1 | MIT | https://github.com/emotion-js/emotion | MUI 스타일링 엔진(전이 의존성) |
| 13 | @dnd-kit/core | 6.3.1 | MIT | https://github.com/clauderic/dnd-kit | 보관함 항목 press-and-hold(2초) 드래그로 서비스 그룹 이동 |

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
| 18 | tslib | 2.8.1 | 0BSD | https://github.com/microsoft/tslib | ← radix-ui, @dnd-kit |
| 19 | @dnd-kit/accessibility | 3.1.1 | MIT | https://github.com/clauderic/dnd-kit | ← @dnd-kit/core |
| 20 | @dnd-kit/utilities | 3.2.2 | MIT | https://github.com/clauderic/dnd-kit | ← @dnd-kit/core |

> 프론트 production 트리 전체(148종, 2026-09-03 `license-checker --production` 실측)는 MIT 137 ·
> Apache-2.0 4 · BSD-3 3 · ISC 2 · 0BSD 1 · BSD-2 1 로만 구성(카피레프트 0). 위 표는 대표 항목이며
> 전체 목록은 `frontend/`에서 `npx license-checker --production --json`으로 재생성한다.

---

## 3. 참고 자산 (AI 모델 / 데이터)

| 자산 | 버전 | 라이선스 | 출처 | 사용 목적 |
|---|---|---|---|---|
| PP-OCRv5 한국어 인식 모델(가중치) | v3.9.2 릴리스 | Apache-2.0 | https://www.modelscope.cn/models/RapidAI/RapidOCR | 백엔드 OCR(RapidOCR) 한국어 인식 — 현재 활성 경로, `backend/scripts/vendor_ocr_models.py`가 해시 검증 후 로컬 벤더링(커밋 제외) |
| Tesseract 학습 데이터 (eng·kor `.traineddata`) | tessdata_fast | Apache-2.0 | https://github.com/tesseract-ocr/tessdata_fast | ⚠️ 레거시(브라우저 OCR, 현재 미사용 경로) — 로컬 벤더링 |
| tesseract.js WASM core | 7.0.0 | Apache-2.0 | https://github.com/naptha/tesseract.js-core | ⚠️ 레거시(브라우저 OCR, 현재 미사용 경로) |
| Pretendard (Variable) | 1.3.9 | OFL-1.1 | https://github.com/orioncactus/pretendard | 본문 폰트(로컬 벤더링) |
| JetBrains Mono | 2.304 | OFL-1.1 | https://github.com/JetBrains/JetBrainsMono | 값·키 모노 폰트(로컬 벤더링) |
| simple-icons | 16.28.0 | CC0-1.0 | https://github.com/simple-icons/simple-icons | 서비스 로고 SVG 6종(Notion·Kakao·GCP·Ollama·GitHub·Stripe) — devDependency, `frontend/scripts/vendor-logos.mjs`가 수정 없이 `frontend/src/assets/logos/*.svg`로 로컬 벤더링해 빌드 산출물에 포함(npm 패키지 `simple-icons` 자체는 런타임에 import하지 않음 — 벤더링된 SVG 파일만 로드) |

> 폰트는 **CDN 대신 빌드 시 로컬 벤더링**(`frontend/scripts/vendor-fonts.mjs` → `public/fonts/`, same-origin 서빙)으로
> 런타임 외부 요청 0(local-first). OFL-1.1 은 permissive(임베드·배포 허용, 폰트 단독 판매 금지·예약명칭 유지).

> ⚠️ 붙임2(AI 모델 활용 명세서)와 연동: OCR 엔진은 **외부 모델 그대로 활용(유형1)**, 파인튜닝 없음. 상세는 OSS-4.

---

## 4. 개발·빌드 전용 (배포물에 미포함 — 참고)

산출물(`dist/`, 백엔드 실행)에는 실리지 않는 도구들. 카피레프트 없음.

- **프론트(devDependencies)**: vite, vitest, oxlint, typescript, @vitejs/plugin-react, @types/*,
  **tailwindcss·@tailwindcss/vite**(빌드타임 CSS — 이들이 끌어오는 `lightningcss`는 MPL-2.0이나
  컴파일된 CSS만 배포되어 산출물에 미포함). dev 트리 라이선스: MIT/Apache-2.0/ISC.
- **백엔드(dev)**: 위 §1-3 참고.
- **데모 자산 생성**(`docs/demo/generate.py`·`make_gif.py`, 개발 전용 — 런타임 아님): **Pillow (HPND, permissive/MIT류)**.
  콘솔 스크린샷 더미 PNG와 README 히어로 GIF 생성에만 사용. 카피레프트 0.
- **데스크톱 런처**(`desktop/`, 선택 실행 — 웹 배포물엔 미포함): **pywebview 6.2.1 (BSD-3-Clause)**.
  전이 pythonnet(MIT)·clr-loader(MIT)·bottle(MIT)·proxy_tools(MIT). WebView2 런타임은 Windows 기본 OS 구성요소. 카피레프트 0.
- **데스크톱 알림**(`desktop/notify.py`, RUNTIME-1): **plyer 2.1.0 (MIT)**. 전이 의존성 없음, Windows 경로는
  순수 stdlib `ctypes`만 사용(`plyer/platforms/win/libs/balloontip.py`). 카피레프트 0.
- **데스크톱 패키저**(빌드 도구, 실행 파일에 도구 코드 미포함): **cx_Freeze**(PSF 계열 permissive) 기본 채택.
  대안 Nuitka(Apache-2.0). PyInstaller(GPL-2.0+예외)는 생성물이 GPL에 묶이지 않으나, permissive 기조상 기본은
  cx_Freeze. 어느 쪽이든 산출 실행 파일의 라이선스는 본 프로젝트 MIT + 의존성 라이선스만 따른다.
- **일회성 스캔 도구**(설치 후 제거): pip-licenses(MIT), license-checker(BSD-3-Clause),
  reuse(Apache-2.0, SPDX 헤더 검사), pip-audit(Apache-2.0, 취약점 스캔). venv/노드모듈에만 설치되며
  `.gitignore` 로 저장소·배포물에서 제외.

---

## 5. 알려진 취약점 점검 (SCA)

> 점검(2026-07-05): 프론트 `npm audit --omit=dev`, 백엔드 `pip-audit`.
> **프론트 production 트리 0건 · 백엔드 0건 — 전체 SCA 클리어.** starlette(런타임)와 pytest(테스트)를
> 모두 패치본으로 업그레이드해 알려진 CVE를 전부 해소했다. 도구 전제: 서버를 `127.0.0.1` 에만 바인딩하는
> **단일 사용자 로컬 도구**이며 엔드포인트는 **작은 JSON 바디만 수신**한다(파일 업로드·멀티파트/폼·정적파일
> 서빙·`HTTPEndpoint`·인증 프록시 없음).

### 5-1. 프론트엔드 (npm, production)

`npm audit --omit=dev` → **0 vulnerabilities**.

### 5-2. 백엔드 런타임 — `starlette` ✅ 해소 (0.41.3 → **1.3.1**)

X41/OSTIF "BadHost" 감사 등으로 보고된 7건. `fastapi 0.115.6` 의 `starlette<0.42` 상한 때문에 패치본에
도달할 수 없어, **`fastapi==0.139.0` + `starlette==1.3.1` 로 업그레이드**해 전부 패치본을 적용했다
(백엔드 테스트 129개 회귀 통과, `pip-audit` 재감사에서 starlette 0건 확인). 아래는 이력 기록.

| ID | 요약 | 최초 수정본 | 현재(1.3.1) |
|---|---|---|---|
| CVE-2025-54121 | 멀티파트 대용량 업로드가 이벤트 루프 블로킹(DoS) | 0.47.2 | ✅ 패치됨 |
| CVE-2025-62727 | `Range` 헤더로 FileResponse/StaticFiles O(n²) CPU DoS | 0.49.1 | ✅ 패치됨 |
| CVE-2026-48817 | `HTTPEndpoint` 에 임의 HTTP 메서드 디스패치(인증 우회) | 1.1.0 | ✅ 패치됨 |
| CVE-2026-48818 | StaticFiles UNC 경로 SSRF/NTLM 유출(Windows) | 1.1.0 | ✅ 패치됨 |
| CVE-2026-48710 (PYSEC-2026-161) | Host 헤더 미검증 → `request.url.path` 오염(경로 인증 우회) | 1.0.1 | ✅ 패치됨 |
| CVE-2026-54282 (PYSEC-2026-248) | `request.url.hostname`/`netloc` 공격자 제어 | 1.3.0 | ✅ 패치됨 |
| CVE-2026-54283 (PYSEC-2026-249) | urlencoded 폼에서 `max_fields`/`max_part_size` 미적용(메모리 DoS) | 1.3.1 | ✅ 패치됨 |

> 업그레이드로 딸려온 신규 전이 의존성 `annotated-doc`(MIT)·`typing-inspection`(MIT)은 permissive 라이선스로
> 카피레프트 정책에 부합(§1-2 반영).

### 5-3. 백엔드 테스트 전용 — `pytest` ✅ 해소 (8.3.4 → **9.0.3**)

| ID | 요약 | 최초 수정본 | 현재(9.0.3) |
|---|---|---|---|
| CVE-2025-71176 | `/tmp/pytest-of-{user}` 예측가능 경로 TOCTOU 레이스(로컬 권한상승/DoS) | 9.0.3 | ✅ 패치됨 |

> `pytest==9.0.3` 로 상향(테스트 129개 회귀 통과). major 업그레이드지만 사용 API(parametrize·fixture·
> raises)에 브레이킹 영향 없음. 배포물과 무관한 테스트 러너다.

### 5-4. 최종 판정

`pip-audit`(백엔드)·`npm audit --omit=dev`(프론트) 모두 **0건**. 런타임·테스트·프론트 전 영역 SCA 클리어.

---

## 재생성 방법

```bash
# 라이선스 (백엔드)
cd backend && ./.venv/Scripts/python.exe -m pip install -q pip-licenses
./.venv/Scripts/python.exe -m piplicenses --format=markdown --with-urls --order=license
# 라이선스 (프론트, 배포물 판정 기준)
cd frontend && npx --yes license-checker --production --summary

# 취약점 SCA (§5)
cd frontend && npm audit --omit=dev
cd backend && ./.venv/Scripts/python.exe -m pip install -q pip-audit && PYTHONUTF8=1 ./.venv/Scripts/python.exe -m pip_audit
```
