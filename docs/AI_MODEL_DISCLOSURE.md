<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# 붙임2 — AI 모델 활용 명세서 (KeyLens)

> 운영규정 9조에 따른 AI 모델 활용 명세. KeyLens는 스크린샷 OCR에 **AI 모델(RapidOCR)** 을 탑재하고,
> 옵트인 기능("이 화면 설명해줘")으로 **사용자가 직접 실행 중인 로컬 LLM(Ollama)** 에 연결할 수 있다
> (미설정 시 이 기능 자체가 비활성화되며, 앱은 이 LLM의 가중치를 전혀 포함하지 않는다).
> ⚠️ 아래 **5번(코딩 보조 AI 비율)** 은 제출 전 작성자가 직접 확인·확정해야 하는 항목이다(빈칸 표시).

---

## 1. AI 모델 탑재 여부 및 유형

| 항목 | 내용 |
|---|---|
| AI 모델 탑재 | **예** — (1) 스크린샷에서 텍스트를 읽는 OCR(RapidOCR, 항상 활성) (2) 화면 영역 설명 기능용 로컬 LLM(Ollama, 옵트인·기본 비활성) |
| 활용 유형 | 둘 다 **유형 1 — 외부에 공개된 사전학습 모델을 그대로 활용** (파인튜닝·재학습 없음) |
| 자체 학습/파인튜닝 | **없음** — 모델 가중치를 수정하지 않고 추론(inference)에만 사용 |

---

## 2. 기반 모델 정보

### 2-1. OCR(RapidOCR) — 항상 활성, 앱에 가중치 포함

| 항목 | 내용 |
|---|---|
| 모델명 | **RapidOCR(PP-OCRv5 한국어 인식 모델)** — 백엔드(로컬 FastAPI, 127.0.0.1)에서 실행 |
| 가중치 | `korean_PP-OCRv5_rec_mobile.onnx`(det·cls 모델은 `rapidocr` 패키지에 번들) |
| 모델 라이선스 | **Apache-2.0**(RapidOCR·PP-OCRv5 가중치 모두 PaddleOCR 프로젝트 산출물) |
| 모델 출처 | RapidOCR: https://github.com/RapidAI/RapidOCR · 가중치: https://www.modelscope.cn/models/RapidAI/RapidOCR(v3.9.2 릴리스) |
| 실행 위치 | **로컬 백엔드(사용자 기기 안, 127.0.0.1)** — 이미지·값이 기기를 떠나지 않음(로컬·프라이버시) |
| 비고 | 초기(CORE-3 이전) 버전은 브라우저 `tesseract.js`(WASM)를 사용했으나, 한글 단일 글자 라벨 오독
  문제로 이 RapidOCR 백엔드 경로로 전면 교체했다 — `frontend/src/ocr/ocr.ts`·`reconstruct.ts`는
  현재 실제 분석 흐름에서 호출되지 않는 레거시 코드로 남아 있다(삭제하지 않은 이유: 유닛 테스트
  `reconstruct.test.ts`가 재구성 로직 자체의 회귀를 계속 검증). 상세 근거는
  `THIRD-PARTY-NOTICES.md`의 "스크린샷 OCR (backend, CORE-3)" 절 참고. |

### 2-2. 화면 설명 기능용 LLM(Ollama) — 옵트인, 앱에 가중치 미포함

| 항목 | 내용 |
|---|---|
| 모델명 | **사용자가 직접 선택** — 앱은 특정 모델을 지정하지 않는다. 운영자가 로컬에 이미 설치·실행 중인
  Ollama 서버의 `OLLAMA_MODEL` 환경변수로 지정한 모델을 그대로 호출한다(예: `llama3.2`, `qwen2.5` 등,
  전부 각 모델 배포처의 사전학습 가중치 그대로 사용 — 파인튜닝 없음). |
| 가중치 | **앱 저장소·배포물에 전혀 포함되지 않음** — 사용자가 자신의 Ollama에 직접 받아둔 모델만 호출 |
| 모델 라이선스 | 앱 코드와 무관(모델별로 다름 — 어떤 모델을 쓸지는 전적으로 사용자 선택이므로 앱이 특정 모델의
  라이선스를 보증하지 않는다) |
| 실행 위치 | **사용자 기기의 로컬 Ollama 서버**(`http://localhost:11434` 기본값) — 클라우드 API 아님, 화면
  텍스트는 Ollama 호출 자체로는 외부로 전송되지 않음(단, 아래 2-3의 Tavily 검색을 함께 켰을 때는
  Ollama의 추측 결과 일부가 별도로 전송된다) |
| 활성 조건 | `OLLAMA_MODEL` 환경변수 미설정 시 이 기능("이 화면 설명해줘" 버튼) 자체가 화면에 나타나지 않음
  — 조용히 저성능으로 동작하는 대신 기능을 완전히 숨김 |
| 호출 코드 | `backend/app/ollama_client.py`(표준 라이브러리 `urllib`만 사용, 새 런타임 의존성 없음) |

### 2-3. 화면 설명 확인용 웹 검색(Tavily) — 옵트인, AI 모델 아님(검색 API)

Ollama가 지식베이스에 없는 서비스를 추측했을 때, 그 추측이 맞는지 확인하기 위해 웹 검색을
쓴다. 모델 자체는 아니지만 위 Ollama 추론과 직결돼 있어 함께 명시한다.

| 항목 | 내용 |
|---|---|
| 서비스 | [Tavily Search API](https://tavily.com) — 제3자 클라우드 서비스(로컬 아님) |
| 활성 조건 | `TAVILY_API_KEY` 환경변수 미설정 시 검색 단계 자체를 건너뛰고 기존처럼 로컬 Ollama
  추측만으로 끝난다(`ai_unverified`) — 이 키가 없다고 화면 설명 기능 자체가 숨겨지진 않는다(Ollama와의
  차이점) |
| **외부로 나가는 데이터** | Ollama가 추측한 **서비스명 텍스트**(예: `"Notion"`)만 검색 쿼리로
  전송된다. 원본 스크린샷 이미지·OCR 전체 텍스트·저장된 키 값은 전송되지 않는다. 추측한 서비스명이
  실제로는 값(시크릿 등)처럼 보이면 애초에 전송을 건너뛴다(`backend/app/explain.py`의
  `_looks_like_value`) |
| 도메인 제한 | 없음 — 검색 결과가 실제로 그 서비스의 공식 문서가 맞는지는 다시 로컬 Ollama가
  재검증한다(신뢰 경계는 도메인 화이트리스트가 아니라 LLM 재검증) |
| 로컬 캐시 | 사용자가 화면에서 "저장"을 눌러 승인한 결과만 `backend/local_discoveries.yaml`
  (git 추적 안 함)에 남는다 — 자동 저장 없음 |
| 호출 코드 | `backend/app/tavily_client.py`(표준 라이브러리 `urllib`만 사용, 새 런타임 의존성 없음) |

---

## 3. 직접 작성한 코드 (추론·활용 로직)

모델 자체는 외부 것을 그대로 쓰되, **모델을 호출하고 그 출력을 활용하는 코드는 전부 직접 작성**했다.

| 구성요소 | 파일 | 라이선스 | 역할 |
|---|---|---|---|
| OCR 호출(RapidOCR, 현재 활성 경로) | `backend/app/ocr.py` | MIT | RapidOCR 호출, 줄 순서 보존 텍스트·박스 좌표 추출 |
| 분류 엔진(모델 출력 활용) | `backend/app/classify/*.py` | MIT | OCR 텍스트 → 맥락 기반 분류 |
| Ollama 호출(화면 설명, 옵트인) | `backend/app/ollama_client.py` | MIT | 로컬 Ollama HTTP API 호출(urllib만 사용) |
| 화면 설명 파이프라인(모델 출력 활용) | `backend/app/explain.py` | MIT | 지식베이스 대조 + 미분류 줄만 Ollama에 배치 질의 |
| OCR 호출·값 정밀 재인식(레거시, 미사용) | `frontend/src/ocr/ocr.ts` | MIT | tesseract.js 호출 — CORE-3에서 RapidOCR로 대체, 현재 실제 흐름에서 미호출 |
| 라벨-값 공간 재구성(레거시, 유닛테스트만 참조) | `frontend/src/ocr/reconstruct.ts` | MIT | word 박스 → 라인 보존 텍스트, 라벨-값 페어링 |
| 자산 로컬 벤더링(레거시 경로용) | `frontend/scripts/vendor-tesseract.mjs` | MIT | WASM·언어데이터 로컬 번들(오프라인·재현성) |

- 코드 저장소: https://github.com/ttogle918/key-manager (MIT)
- **다른 도구의 탐지 패턴/코드를 포팅하지 않았다.** 키 포맷 정규식은 각 서비스 공식 문서 기준으로 직접 작성(AGPL TruffleHog 포팅 금지 규칙 준수).

---

## 4. 데이터셋 / 가중치 배포

| 항목 | 내용 |
|---|---|
| 학습 데이터셋 공개 | **해당 없음** (파인튜닝하지 않음) |
| 파인튜닝 가중치 배포 | **해당 없음** (기반 모델을 그대로 사용) |
| 사용한 사전학습 가중치(OCR) | RapidOCR PP-OCRv5 한국어 인식 모델(Apache-2.0) — 저장소에는 커밋하지 않고 `backend/scripts/vendor_ocr_models.py`가 해시 검증 후 로컬 벤더링(`.gitignore`), 출처·라이선스는 THIRD-PARTY-NOTICES.md/SBOM.md에 기록 |
| 사용한 사전학습 가중치(화면 설명 LLM) | **앱 저장소에 전혀 포함되지 않음** — 사용자가 자신의 Ollama에 별도로 받아둔 모델을 그대로 호출(2-2 참고) |

---

## 5. 코딩 보조 AI 활용 (운영규정 9조⑤)

> ⚠️ **작성자 확인 필요** — 아래는 정직하게 기재해야 하며, AI가 작성한 코드의 동작 원리를 설명 가능한 수준으로
> 리뷰했음을 전제로 한다(이해 부족 시 감점 가능). 대략치라도 개발 과정에서 가늠해 채운다.

| 항목 | 내용 |
|---|---|
| 사용한 코딩 보조 AI | Claude Code (Anthropic) |
| AI 작성 코드 비율(대략) | `________ %` (작성자 기입) |
| 핵심 로직 이해·설명 가능 여부 | 분류 2단계(Stage1/2)·암호화(Argon2id/AES-GCM)·인증 세션·OCR 재구성 등 핵심 경로는 직접 설명 가능하도록 리뷰함 (☐ 확인) |
| 검증 | 백엔드 pytest 253개 · 프론트 tsc/oxlint/build · 브라우저 E2E — AI 작성 코드 포함 전 경로를 테스트로 검증 |

---

## 요약

KeyLens의 AI 모델 활용은 두 가지 모두 **유형 1(외부 사전학습 모델 그대로 활용, 파인튜닝 없음)** 이다.
- **OCR(RapidOCR, 항상 활성)**: 로컬 백엔드에서 추론(Apache-2.0), 모델을 호출·활용하는 코드는 전부
  직접 작성(MIT). 초기 버전(Tesseract/브라우저 WASM)은 CORE-3에서 대체돼 현재 비활성 레거시 코드로만
  남아 있다.
- **화면 설명 LLM(Ollama, 옵트인)**: 앱은 어떤 모델 가중치도 포함하지 않는다 — 사용자가 직접 실행 중인
  로컬 Ollama에 연결만 하며, `OLLAMA_MODEL` 미설정 시 기능 자체가 비활성화된다.

데이터셋·가중치 배포는 해당 없음. 라이선스 충돌 없음(전부 permissive, 사용자가 선택하는 Ollama 모델의
라이선스는 앱 코드와 무관).
