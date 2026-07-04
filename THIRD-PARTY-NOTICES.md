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

> Apache-2.0 구성요소가 다수이므로, Apache-2.0 §4의 고지 의무를 위해 각 저장소의 NOTICE/LICENSE 원문을 함께 참고하라.
> 전문: https://www.apache.org/licenses/LICENSE-2.0
