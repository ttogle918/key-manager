<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# THIRD-PARTY NOTICES

이 프로젝트(MIT)는 다음 서드파티 구성요소를 사용합니다. 각 구성요소는 해당 라이선스 조건을 따릅니다.
대부분 허용적(permissive) 라이선스이며, GPL/AGPL 같은 **강한 카피레프트는 전혀 포함하지 않습니다**.
`backend/app/ocr.py`(CORE-3 백엔드 OCR) 경로에 한해 **약한 카피레프트(LGPL/MPL) 3건**을 의도적으로
포함합니다 — 아래 "스크린샷 OCR(backend)" 절에 왜 안전한지 근거를 명시합니다.

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

## 스크린샷 OCR (backend, CORE-3 — 한국어 라벨 인식 정확도 개선)

브라우저 tesseract.js(위 절)는 한글 단일 글자 라벨("키"/"앱")을 반복 오독해 Kakao 4종 키 중 2종이
`unknown`으로 빠졌다. RapidOCR의 한국어 PP-OCRv5 인식 모델로 교체 실험 결과 4종 전부 정확히 인식해
이 경로를 **로컬 백엔드(127.0.0.1)** 로 옮겼다 — 이미지는 여전히 이 기기 안에서만 처리되고 디스크에
저장되지 않는다(로컬 우선 원칙·대회 규정 제9조 로컬 구동 필수 그대로 유지).

### rapidocr
- 버전: 3.9.2
- 라이선스: **Apache-2.0**
- 출처: https://github.com/RapidAI/RapidOCR
- 용도: PP-OCR(det·cls·rec) ONNX 모델을 감싸는 추론 래퍼. 코드 복사 없이 공개 API(`RapidOCR`)만 호출.

### onnxruntime
- 버전: 1.29.0
- 라이선스: **MIT**
- 출처: https://github.com/microsoft/onnxruntime

### python-multipart
- 라이선스: **Apache-2.0**
- 출처: https://github.com/Kludex/python-multipart
- 용도: FastAPI `UploadFile`(스크린샷 업로드) 파싱에 필요.

### PP-OCRv5 한국어 인식 모델 (가중치)
- 파일: `korean_PP-OCRv5_rec_mobile.onnx` (SHA256 `cd6e2ea5…773c9b`, 벤더링 시 검증)
- 라이선스: **Apache-2.0** (PaddleOCR 프로젝트 산출물)
- 출처: https://www.modelscope.cn/models/RapidAI/RapidOCR (v3.9.2 릴리스)
- 비고: `backend/scripts/vendor_ocr_models.py`가 해시 검증 후 `backend/app/ocr_models/`에 로컬
  벤더링한다(커밋 제외, `.gitignore`). det(글자영역 검출)·cls(각도분류) 모델은 `rapidocr` 패키지에
  이미 번들되어 별도 벤더링이 필요 없다(둘 다 Apache-2.0, 동일 출처).

### 확인된 전이 의존성(전부 permissive)
Shapely·antlr4-python3-runtime·omegaconf·protobuf (BSD-3-Clause) · numpy (BSD-3-Clause AND
0BSD AND MIT AND Zlib AND CC0-1.0, 전 구성요소 허용목록 내) · pyclipper·six (MIT) · Pillow
(MIT-CMU) · flatbuffers·requests (Apache-2.0).

### 약한 카피레프트 3건 — 의도적 포함(안전 근거 명시)

- **tqdm** (rapidocr 필수 전이 의존성) — 라이선스 **MPL-2.0**(핵심 코드, 일부 deprecated shim
  파일만 MIT). **파일 단위(weak) 카피레프트**: MPL이 요구하는 건 "MPL 커버 파일 자체를 수정해서
  재배포할 때 그 수정 파일을 공개"뿐이다. 우리는 tqdm 소스를 수정하지 않고 pip 의존성으로 그대로
  사용하므로 이 프로젝트(MIT) 코드에는 전염되지 않는다.
- **certifi** (rapidocr → requests 전이 의존성) — 라이선스 **MPL-2.0**. CA 루트 인증서 번들만
  담은 데이터 패키지로, requests가 HTTPS 검증용으로 import해 그대로 쓴다. tqdm과 동일한 이유로
  안전 — 소스를 수정하지 않고 pip 의존성으로만 사용, 파일 단위 카피레프트라 이 프로젝트(MIT) 코드로
  전염되지 않는다. (참고: `cryptography` 자체는 certifi를 끌어오지 않는다 — 아래 "cryptography"
  절 참고. certifi는 rapidocr가 유일한 경로다.)
- **opencv-python** (rapidocr 필수 전이 의존성) — 파이썬 바인딩 코드 자체는 Apache-2.0이나, Windows
  휠에 **FFmpeg(LGPL-2.1)** 가 동봉된다. 단, FFmpeg는 cv2 본체에 정적으로 박히지 않고 **별도의
  교체 가능한 플러그인 DLL**(`cv2/opencv_videoio_ffmpeg500_64.dll`)로 동적 로드된다 — OpenCV팀이
  LGPL의 "재링크 가능성 보장" 요건을 만족시키려 의도적으로 설계한 구조다. cx_Freeze 데스크톱 패키징도
  이 DLL을 실행파일과 분리된 개별 파일로 배치해(정적 병합 없음) 재교체 가능성이 유지된다.
- CLAUDE.md 규칙: **강한 카피레프트(GPL/AGPL)는 여전히 절대 금지**. 위 세 건은 "미수정 의존성
  사용 + 재링크 가능 구조 유지"라는 조건을 만족하는 예외로, 새로 카피레프트 의존성을 볼 때마다
  이 기준으로 개별 판단한다(자동으로 전부 허용되는 게 아님). CI(`ALLOWED_WEAK_COPYLEFT`)도 이
  두 패키지명(tqdm, certifi)만 명시 허용한다 — opencv-python은 pip-licenses에 라이선스가
  Apache-2.0으로만 잡혀 그 검사에 걸리지 않는다(LGPL 부분은 별도 바이너리 DLL이라 위 근거로 대신
  기록).

## 암호화 저장소 (backend, VAULT-1)

### cryptography
- 버전: 50.0.1 (49.0.0은 PYSEC-2026-3552 취약점이 있어 패치본으로 고정 — pip-audit)
- 라이선스: Apache-2.0 OR BSD-3-Clause (듀얼 — 본 프로젝트는 **BSD-3-Clause를 선택 적용**)
- 출처: https://pypi.org/project/cryptography/50.0.1/ · https://github.com/pyca/cryptography
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
| @mui/material | 9.3.1 | MIT | https://github.com/mui/material-ui — 분석 결과 요약 DataGrid |
| @mui/x-data-grid | 9.12.0 | **MIT**(Community 등급) | https://github.com/mui/mui-x — ⚠️ Pro/Premium/Enterprise 등급은 유료 상용 라이선스라 미사용, Community(`@mui/x-data-grid`, 접미사 없음)만 사용 |
| @emotion/react · @emotion/styled | 11.14.0 · 11.14.1 | MIT | https://github.com/emotion-js/emotion — MUI 기본 스타일링 엔진(전이 의존성) |

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
