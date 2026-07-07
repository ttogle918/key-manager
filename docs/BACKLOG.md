<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# BACKLOG — 자격증명 분류·보관 도구 (가칭: KeyLens)

> **한 줄 정의**: 스크린샷·URL을 던지면 "이건 Notion API 키, 이건 database ID"처럼 **맥락으로 정체를 가려** 공식 변수명에 매핑하고, 암호화해 나만 볼 수 있게 보관하는 개인용 도구.
> **공모전**: 오픈소스 개발자대회 자유과제(보안). 접수 ~7/17 · 제출 8/27 · 2차 기능테스트/라이선스 검증 있음.
> **참가 형태**: 솔로. → 코드 60% / 제출물(영상·보고서·OSS 정리) 40% 시간 배분 전제.

## 전제 — 아키텍처 & 스택 (전부 permissive 라이선스)

- **형태**: 로컬 우선(local-first). 데이터는 사용자 기기에 **SQLite**로 암호화 저장. 외부 서버 없음(로컬 백엔드만).
- **백엔드**: FastAPI (MIT) — 분류·OCR·암호화 로직
- **프론트**: React + TypeScript (MIT)
- **OCR**: Tesseract 또는 PaddleOCR (Apache-2.0) — ⚠️ 클라우드 OCR 대신 OSS 사용(라이선스·오프라인·프라이버시)
- **암호화**: `cryptography` (BSD/Apache) — Argon2id(KDF) + AES-256-GCM
- **정규식 참고**: Gitleaks 패턴 (MIT, 출처 표기) — ⚠️ TruffleHog(AGPL) 코드/패턴 포팅 금지
- **차별점의 위치**: `CORE-2` 맥락 기반 분류(라벨 + URL + 서비스 지식베이스). 여기가 데모 magic moment.

## 스프린트 편성 (6/23 – 8/27)

| 스프린트 | 기간 | 테마 | 주요 TASK | L 개수 |
|---|---|---|---|---|
| **S1** | 6/23–7/6 | 뼈대 + 쉬운 분류 + 연결 | ✅CORE-1, ✅CORE-4, ✅VAULT-0, ✅UI 골격, ✅INTEG-1 | 0 |
| **S2** | 7/7–7/20 | **맥락 기반 분류(차별점)** | ✅CORE-2, ✅CORE-3(OCR), ✅DEMO-1 | 1 (CORE-2) |
| **S3** | 7/21–8/3 | 금고 + 인증 + 조회 | ✅VAULT-1, ✅VAULT-2, ✅UI-2 | 1 (VAULT-1) |
| **S4** | 8/4–8/17 | 신뢰 기능 + 안정화 | ✅CORE-5, ✅TRUST-1, ✅TRUST-2, ✅SYNC-0, ✅OSS-1 | 0 |
| **제출** | 8/18–8/27 | 제출물 + 재현성 | ✅OSS-2, 🔄OSS-3, OSS-4 | 0 |

> **⚠️ 용량 점검(솔로)**: 배치 원칙 상 L은 스프린트당 최대 1개로 잡았다(S2·S3 각 1개). S4 이후는 신규 L 없이 **안정화·신뢰 기능·제출물**로만 채워, 막판 과적을 방지한다. TRUST 계열(validity/expiry)과 SYNC-0은 **stretch**로 표시 — S4에서 시간이 부족하면 가장 먼저 잘라낼 후보다(잘라도 MVP는 성립).

### 진행 현황 (2026-07-05 기준 — 일정 대비 크게 앞섬: S3까지 완료)

- ✅ **분류 엔진(차별점)**: CORE-1(값 기반)·**CORE-2(맥락 기반, 프로젝트 심장)**·CORE-3(브라우저 OCR + 값 정밀 재인식)·CORE-4(지식베이스 **9종**: Notion/Kakao/GCP/OpenAI/Ollama/GitHub/AWS/Slack/Stripe)·DEMO-1(더미 스크린샷+골든 픽스처) 완료.
- ✅ **확장성 실체화**: 프론트가 부팅 시 `/knowledge`를 읽어 종류맵·서비스 목록을 **동적 구성** → 새 서비스는 YAML 하나로 백엔드·프론트 양쪽 자동 반영(코드 수정 0). GitHub/AWS/Slack/Stripe 4종을 프론트 코드 0줄로 추가해 증명.
- ✅ **금고(보안 실체)**: VAULT-1(Argon2id + AES-256-GCM + SQLite 암호문만)·VAULT-2(세션 인증·자동잠금·실패지연·감사이력·값 교체) 완료 — **브라우저 E2E 검증 통과**.
- ✅ **연결·UI**: INTEG-1(프론트↔백엔드 실연결)·UI-1/UI-2(실 금고·인증 연결)·CORE-5(.env 내보내기) 완료.
- ✅ **제출 준비**: OSS-2(라이선스 카피레프트 0·reuse lint 통과·SBOM)·OSS-3(dev 스크립트·README, 새VM 검증만 잔여) 대부분 완료.
- ✅ **보안 감사**(SECURITY_REVIEW.md): 상·중·하 실행 가능 항목 전부 해소(허위 보안표시·마스킹·감사이력·회전 등). ⏳ 남은 건 제출주간 성격(새 VM·포털 도구)뿐.
- ✅ **신뢰 기능(stretch 선반영)**: TRUST-1(키 유효성 검증 — read-only 1회 호출 → active/invalid/unknown, KB `verify:` 확장형)·TRUST-2(만료일 수동 입력 + JWT exp 자동 추출 + 임박 상단 정렬) 완료.
- ✅ **멀티 기기(stretch 선반영)**: SYNC-0(암호화 금고 번들 내보내기/가져오기 — 교체·병합, 제로 널리지 유지) 완료. 서버리스 멀티 기기의 최소 단위 확보.
- ✅ **배포·데스크톱**: 배포/설치 온보딩 문서 강화(git clone·요구사항·트러블슈팅)·CONTRIBUTING.md, **데스크톱 앱**(PyWebView `desktop/app.py` — 네이티브 창, API+SPA same-origin 서빙, 100% 로컬), **실행 파일 패키징**(`desktop/setup.py` cx_Freeze=permissive; app.py frozen 감지 + `KEYLENS_KNOWLEDGE_DIR` env) 완료 — **`KeyLens.exe` 빌드 실증**(번들 KB 9종·SPA·분류까지 정상 서빙 확인). GUI 창 시각 확인만 실기기 몫.
- ✅ **호스팅 로드맵**: 결과보고서에 "왜 로컬인가 / 웹 호스팅하려면 클라이언트 E2E 암호화 선행 / 랜딩 페이지는 안전" 설계 근거(§8.5) 추가.
- ✅ **CI(GitHub Actions)**: push/PR마다 백엔드 pytest·프론트 build/vitest/oxlint·**reuse lint·카피레프트 0(pip-licenses/license-checker, clean 런타임 env)**·취약점(pip-audit/npm audit) 자동 실행 + README 배지. 대회 2차 검증(라이선스·재현·테스트·보안)을 자동화·상시화.
- ✅ **KB 확장**: GCP 4종(api_key·OAuth id/secret·service_account_json)으로 확장 — 프론트 코드 0줄(=/knowledge 동적).
- **남은 큰 항목**: **OSS-4**(3분 영상 + 결과보고서 + AI 명세서).
- ✅ **키 발급 도움말**: **GUIDE-1 A·B 완료** — KB 도움말(9종)·`/knowledge` 노출·`KeyHelp`(발급받기/문서 링크·발급 방법). **B(딥링크)**: `{project}` 치환(ID 형태만, 아니면 안전 폴백) + 도메인 화이트리스트(`isAllowedUrl`)로 오픈리다이렉트 차단.
- ✅ **키 보안 등급·연동**: **GUIDE-2 대부분 완료** — KB에 노출등급(public/secret)·유출 피해·보안 팁(22종), `ExposureBadge`(🔒 노출 금지), KeyHelp에 피해·팁, 상태 연동(검증 invalid→재발급, 회전 모달→발급). 잔여: TRUST-2 만료→재발급·충돌 카드 구분법(선택).
- **제안(후보)**: 없음(핵심 소진). stretch 3종(TRUST-1/2, SYNC-0) + GUIDE-1/2 전부 반영.
- **상시화**: OSS-2 라이선스 검증은 의존성 추가 때마다 수행(`certifi`=MPL 제거, `lightningcss`=MPL 재분류 등 상시 해소).

---

## EPIC-CORE — 분류·매핑 엔진 (프로젝트의 심장)

### CORE-1 🟠 값 기반 분류기 (Stage 1, 쉬운 키) — ✅ 완료(범위 축소)
- **중요도**: 🟠 High | **스프린트**: S1 | **의존성**: 없음 | **사이즈**: M | **상태**: ✅ 커밋 `413f816`
- **배경**: 접두사가 명확한 키(OpenAI `sk-`, GitHub `ghp_`, AWS `AKIA`, Google `AIza`, Slack `xoxb-`)는 값만으로 100% 식별 가능. 이건 "쉽고 흔한" 영역이라 빠르게 끝내고 차별점(CORE-2)에 시간을 몰아준다.
- **구현 노트**: 별도 `detectors/value_rules.py` 대신 **지식베이스의 `value_regex`로 통합**했다(`backend/app/classify/stage1.py`). 값 규칙 = KB 파일. 그래서 검출 범위가 KB에 등록된 접두어(OpenAI/GCP/Notion/OpenAI org)로 한정된다.
- **하위 할일**
  - **[Engine] 값 기반 분류 (`backend/app/classify/stage1.py`)**
    - [x] KB `value_regex` 기반 접두어 키 식별 (OpenAI `sk-`/`org-`, GCP `AIza`, Notion `secret_`/`ntn_`)
    - [x] 접두어 없는 값(UUID·32hex)은 단정 없이 `unknown`으로 안전 분류
    - [x] 엔트로피 보조 판정(`_looks_secret`)으로 unknown 후보 필터
  - **[Engine] 분류 결과 스키마 확정**
    - [x] 출력 `ClassifiedItem`: `{value, masked, service, kind, official_env_name, confidence, format, source, stage, meta}`
  - **[결정] 검출 전용 값 규칙 확장 범위** — ✅ **결정: 별도 `value_rules` 대신 KB YAML로 추가**(아키텍처 일관성 + 확장성 증명)
    - [x] GitHub `ghp_`/`github_pat_`·AWS `AKIA`/`ASIA`·Slack `xoxb-`/`xoxp-`·Stripe `sk_`/`rk_`/`pk_` 를 `knowledge/{github,aws,slack,stripe}.yaml` 로 추가(총 9종). 정규식은 공식 문서 기준 직접 작성, 출처는 `THIRD-PARTY-NOTICES.md` 기록. AWS 시크릿(접두어 없음)은 Stage2 라벨 맥락으로만.
- **테스트 체크리스트**
  - [x] 🧪 `sk-...` 입력 → `openai/api_key/OPENAI_API_KEY` 반환
  - [x] 🧪 무작위 문자열/평문 → 결과 없음, 애매값은 `unknown`(오식별 금지)
  - [x] ✅ 값 기반 4종(OpenAI api/org·GCP·Notion) 더미 키 → 올바른 official_env_name 매핑
  - [x] ✅ GitHub/AWS/Slack/Stripe 추가 접두어 매핑 — `test_new_services.py` 13케이스(값 매칭·오탐 방지·sk_/sk- 구분)

### CORE-2 🔴 맥락 기반 분류 (Stage 2, 차별점) — ✅ text·URL 완료(OCR 입력경로 대기)
- **중요도**: 🔴 Critical | **스프린트**: S2 | **의존성**: CORE-1, CORE-4(지식베이스) *(CORE-3/OCR과 분리)* | **사이즈**: L *(text·URL 부분은 M)* | **상태**: ✅ `stage2.py`, pytest 28개
- **배경**: 노션 database ID·data source ID·page ID는 전부 동일한 32자 UUID라 **값만으론 구분 불가**. 기존 도구(SecurityWall 등)가 정확히 여기서 손든다. 라벨·URL 구조 같은 **출처 맥락**으로 가려내는 게 이 프로젝트의 존재 이유.
- **⚠️ 순서 변경(리스크 축소)**: OCR(CORE-3)에 물려두지 않는다. `/analyze`가 이미 **text·URL을 받으므로**, 붙여넣은 텍스트 라벨과 URL 구조만으로 Stage2 로직을 **먼저 완성·증명**한다(라벨 사전 대조 + `url_patterns` 매칭 + 신호 가중). OCR은 "이미지 → 텍스트+라벨"을 만들어 이 파이프라인에 **먹이는 입력 경로**로 나중에 붙인다 — 차별점이 OCR 안정성에 인질로 잡히지 않게.
- **하위 할일**
  - **[Engine] 맥락 신호 수집기 (`backend/app/classify/stage2.py`)**
    - [x] 라벨 매칭: 값 주변 텍스트(현재줄+바로 위 줄)를 KB `label_patterns`와 대조(값 기반 아닌 종류만)
    - [x] URL 구조 매칭: `url_patterns`로 위치 도출(`?v=` 앞=database_id 강함 / 마지막 세그먼트=page_id 약함)
    - [x] 신호 압축 → confidence(강함=high/약함=medium), 여러 종류로 갈리면 `conflict` + `options`
  - **[Engine] Stage1 → Stage2 파이프라인 연결 (`pipeline.py`)**
    - [x] Stage1 high 값은 skip, 애매값만 Stage2로. 값 기준 병합(Stage2가 unknown 대체)
    - [x] 계약 확장: `ClassifiedItem.conflict/options` + 프론트 매핑(`map.ts`, 충돌 카드로 연결)
- **테스트 체크리스트**
  - [x] 🧪 노션 DB URL → `database_id`(high), page URL → `page_id`(medium) 구분
  - [x] 🧪 라벨(`Database ID`/`REST API 키`) 옆 값 → 해당 종류 매핑 (한글 라벨 pytest 통과)
  - [x] ✅ 신호 충돌(data_source 라벨 vs page URL) → `conflict`+선택지, 단정 안 함
  - [x] 스크린샷(OCR) 경유 라벨 — CORE-3(브라우저 tesseract.js)가 이 파이프라인에 연결됨

### CORE-3 🟠 OCR 파이프라인 (스크린샷 → 텍스트+라벨) — CORE-2의 *입력 경로* — ✅ 브라우저 OCR 완료
- **중요도**: 🟠 High | **스프린트**: S2(후반) | **의존성**: DEMO-1(테스트 이미지) | **사이즈**: M~L *(라벨-값 공간 페어링이 난이도 핵심 — L 가능성*) | **상태**: ✅ tesseract.js(클라이언트) — vitest 8개 + 실제 이미지 E2E
- **배경**: 차별점의 입력단. 핵심은 단순 텍스트가 아니라 **값과 라벨의 위치 관계**를 보존하는 것(라벨이 분류 단서이므로). **CORE-2가 완성된 뒤** 그 파이프라인에 "이미지→텍스트+라벨"을 먹이는 역할 — CORE-2를 막지 않는다.
- **⚠️ 방식 결정**: `ocr_node.py`(파이썬 백엔드) 대신 **브라우저 클라이언트 OCR(tesseract.js, Apache-2.0)**. "모든 분석은 이 기기 안에서" 프라이버시·서버리스 방향과 일치, 파이썬 의존성 0. 라이선스 심사 통과(THIRD-PARTY-NOTICES.md).
- **하위 할일**
  - **[Engine] `frontend/src/ocr/` (tesseract.js)**
    - [x] tesseract.js 연동: 이미지 → word 박스(text+bbox), 한글+영문 동시 인식 (`ocr.ts`)
    - [x] 라벨–값 페어링: word 박스를 행으로 그룹핑(같은 행/바로 위 행 보존) → Stage2 입력 텍스트 (`reconstruct.ts`)
    - [x] 노이즈 정리(마스킹 `••••` → `[마스킹됨]`, 복사/표시 버튼 등 UI 잡음 제거)
    - [x] 출력을 CORE-2 Stage2 입력 형식(라인 보존 text)에 맞춰 기존 `/analyze`로 병합
    - [x] 재현성: WASM core·worker·traineddata 로컬 벤더링(`scripts/vendor-tesseract.mjs`) — 런타임 CDN 미사용
  - **[Engine] 전처리 / 값 정확도** — 조사 완료, 방향 전환
    - [x] 재구성 개선: 구두점에서 쪼개진 토큰 간격 기반 재결합(`6789. Dumm`→`6789.Dumm`) — 실측 win, vitest
    - [x] 🔬 이미지 전처리 실험(grayscale·대비·sharpen·2x확대·Otsu 이진화) → **채택 안 함**: 한글 단일글자("키"→"7\|", "앱"→"2/&")·base62 `1↔i` 오독은 모델 한계라 개선 안 되고, 공격적 변형은 오히려 퇴행(sharpen=환각 `tn)_`, Otsu=hex `0→@`). 고DPI 스크린샷은 전처리 이득 없음.
    - [x] **값 전용 정밀 재인식**: 값 토큰 bbox 영역만 PSM(단일 라인)+charset whitelist 로 2차 인식(`ocr.ts refineValues`). 실측: 실제 Ollama 키 끝자리 `i`→`1` 오독 교정(57/57자 정답). **길이 가드**(1차와 같은 길이일 때만 채택)로 kakao 퇴행(33≠32) 자동 거부. reconstruct 가 `valueTokens{text,bbox}` 노출, vitest.
    - [x] **값 신뢰도 플래깅 UX**: OCR 이 이어붙인 이음매(불확실 지점)를 결과 카드에 빨간 `v` 표식 + 토스트로 안내(경계·공백 기반, 값은 복붙 권장). `reconstruct().flagged` → 카드. vitest.
    - [x] **서비스 분류 정확도**: Ollama 지식베이스 추가 → 실제 스크린샷이 `OLLAMA_API_KEY`로 분류(위 CORE-4 참고)
- **테스트 체크리스트**
  - [x] 🧪 노션 통합 설정 스크린샷 → "Database ID" 라벨+값 페어 추출 → `NOTION_DATABASE_ID`(high) E2E 확인
  - [x] 🧪 마스킹된 값(`secret_••••`) → `[마스킹됨]` 치환, 가짜 값 분류 생성 안 함 (bbox 경로 vitest)
    - ⚠️ 한계: OCR이 `••••`를 글자로 오독하면 마스킹 감지 불가 — 단, 이 경우도 값 정규식 불일치라 unknown(오분류 없음). 전처리(후속)로 개선 여지.
  - [x] ✅ 한글/영문 라벨 혼재(카카오 다중 키) 각 줄 보존 vitest

### DEMO-1 ⚪ 데모/테스트 스크린샷 세트 (`docs/demo/`) — ✅ 완료
- **중요도**: 🟠 High | **스프린트**: S2 | **의존성**: 없음 | **사이즈**: S | **상태**: ✅ 스크린샷 4장 + 골든 OCR 픽스처, pytest
- **배경**: CORE-3(OCR 테스트)와 OSS-4(영상 magic moment)가 **실제 콘솔 스크린샷**을 공유한다. 루트 README도 `docs/demo/`를 참조. 만드는 태스크가 없어 신설.
- **하위 할일**
  - [x] Notion 통합 설정 / Kakao 콘솔(4종 키) / GCP API 키 / OpenAI 키 화면을 **더미 값으로** 재현 — `docs/demo/*.png` + 재현 스크립트 `generate.py`(Pillow, 개발전용)
  - [x] ⚠️ 전부 가짜 값(placeholder) — `generate.py`가 지식베이스 정규식에 맞춰 생성하며 실제 키 아님
  - [x] OCR 회귀 픽스처로 연결: 골든 재구성 `backend/tests/fixtures/demo/*.recon.txt` + `test_demo_fixtures.py`(분류 계약, `⊆`), 재생성 `npm run fixtures:ocr`
  - [ ] ⏸ 한계: `kakao.png` JS/Native 키는 한글 단일 글자("키"/"앱") OCR 오독으로 미검출(7/9) — CORE-3 전처리 후속에서 개선

### CORE-4 🟠 서비스 지식베이스 (선언적 정의) — ✅ 완료(GCP 일부)
- **중요도**: 🟠 High | **스프린트**: S1(앞당김) | **의존성**: 없음 | **사이즈**: M | **상태**: ✅ 커밋 `413f816`
- **배경**: "각 서비스의 키 종류·라벨·URL 패턴·공식 변수명"을 코드가 아니라 **데이터(YAML/JSON)**로 정의해, 새 서비스 추가가 PR 한 건으로 끝나게 한다. 오픈소스 기여 유도 포인트이자 확장성의 핵심.
- **하위 할일**
  - **[Data] `knowledge/*.yaml` 스키마 설계**
    - [x] 필드: `service, credentials:[{kind, label, label_patterns, url_patterns, value_regex?, official_env_name, expiry_known}]` + `_SCHEMA.md`
    - [x] 초기 4종: **Notion**(api/database/data_source/page), **Kakao**(rest/js/admin/native), **GCP**(api_key), **OpenAI**(api_key/org_id)
    - [x] **Ollama**(api_key) 추가 — `<32hex>.<24base62>` 값기반. 실제 스크린샷 E2E로 `OLLAMA_API_KEY` 분류 확인(코드수정 0, YAML 1개 + 프론트 서비스맵)
    - [x] GCP `oauth_client_id`(→GOOGLE_CLIENT_ID)·`oauth_client_secret`(GOCSPX-→GOOGLE_CLIENT_SECRET) 값 기반 + `service_account_json`(JSON이라 라벨 맥락 전용→GOOGLE_APPLICATION_CREDENTIALS) 종류 추가. GCP 4종으로 확장(총 credential 22). 프론트 코드 0줄(=/knowledge 동적)
  - **[Engine] 로더 + 검증**
    - [x] 시작 시 YAML 로드·pydantic 스키마 검증, service·official_env_name 중복 에러, 정규식 컴파일 검증
  - **[OSS] `CONTRIBUTING.md` — "새 서비스 추가법"** — ✅ 완료
    - [x] YAML 한 개 추가 → PR 절차·체크리스트·정규식 출처 규칙(TruffleHog/AGPL 금지)·더미 위생·테스트 예시
- **테스트 체크리스트**
  - [x] 🧪 지식베이스 로드·검증 통과, 중복 official_env_name 차단
  - [x] ✅ `value_matchers`가 접두어 명확 종류만 포함(UUID/hex 종류 제외) 검증
  - [ ] 🧪 잘못된 스키마 YAML → 명확한 에러로 기동 실패 (엣지 테스트 보강)

### CORE-5 🟡 `.env` 내보내기 / 변수명 매핑 확정 — ✅ 완료(VAULT-2에서 실연결)
- **중요도**: 🟡 Medium | **스프린트**: S4 | **의존성**: CORE-2, VAULT-1 | **사이즈**: S | **상태**: ✅ EnvModal + 값 복호화 fetch 연결
- **배경**: 분류·저장된 키들을 표준 변수명으로 `.env` 형태로 내보내 실제 개발에 바로 쓰게 한다. (※ dotenv/EnvKey의 런타임 주입까지는 범위 밖 — 내보내기까지만, 스코프 사수)
- **하위 할일**
  - [x] 선택한 키들 → `KEY=VALUE` 텍스트/파일 내보내기 — 인증(잠금 해제) 상태에서 값 복호화 fetch(`event=export` 이력 기록) 후 `envText()` 생성(복사·다운로드·그룹별)
  - [x] 내보내기 시 "값이 평문으로 포함됨 — .gitignore 필수" 경고 표시(EnvModal)
- **테스트 체크리스트**
  - [x] 🧪 키 선택 → 올바른 official_name으로 `.env` 생성(브라우저 저장·조회 E2E에서 확인)
  - [x] ✅ 미인증(잠금) 상태에서는 내보내기 차단(값 401 → 건너뜀)

### GUIDE-1 🟡 키 발급·역할 도움말 (지식베이스 주도) — ✅ A·B 완료
- **중요도**: 🟡 Medium(생활 편의) | **스프린트**: S4 이후 | **의존성**: CORE-4(지식베이스), INTEG-1(`/knowledge` 동적) | **사이즈**: S(기본)~M(딥링크 포함)
- **배경**: GCP·AWS·Kakao 등은 **키 발급 경로가 헷갈리고**("이 키가 무슨 역할인지", "어디서 발급받는지" 모름), 콘솔 UI가 서비스마다 제각각이다. KeyLens는 이미 서비스별 지식베이스가 있으므로, **"이 키의 역할 + 발급 바로가기 + 공식 문서"를 KB에 선언**하면 분류·보관을 넘어 **발급까지 안내**하는 도구가 된다. 확장성(YAML 하나로 서비스 추가)·대회 "생활 편의" 각도와 정합. 프론트는 `/knowledge` 동적 소비라 **코드 0줄**로 반영된다.
- **관찰(설계 근거)**: 여러 콘솔 URL은 **가운데 ID만 바뀐다**(예: `developers.kakao.com/console/app/{app_id}/...`, `console.cloud.google.com/apis/credentials?project={project_id}`). → `issue_url`에 **플레이스홀더**를 두고, 항목의 저장된 `project`/감지된 ID를 알면 채워서 **바로 그 페이지로 딥링크**, 모르면 서비스 일반 콘솔로 폴백.
- **하위 할일 (A: 기본)**
  - [ ] **[Data] KB 스키마 확장** (`Credential`/`Service`, 전부 선택 필드 — 하위호환)
    - [x] `role`: 종류별 역할 한 줄(노출 가능/서버 전용 명시) — `Credential.role`
    - [x] `issue_url`: 발급 콘솔 바로가기 — `Credential.issue_url`(GCP 서비스계정 등 종류별, 없으면 `console_url` 폴백)
    - [x] `docs_url`: 공식 문서 링크 — `Credential.docs_url`
    - [x] `steps`: 발급 단계 2~3줄 — `Service.steps`(서비스 단위로 이동)
    - [x] `prereq`: 사전조건 — `Service.prereq`
    - [x] (서비스 레벨) `console_url`: 서비스 일반 콘솔 폴백 — `Service.console_url`
  - [x] **[Data] 9종 KB에 값 채우기** — 병렬 리서치 에이전트 4개로 공식 문서 기준 수집, `knowledge/*.yaml` 채움
  - [x] **[Engine] `/knowledge` 노출** — 서비스(console_url/steps/prereq)·종류(role/issue_url/docs_url) 메타 추가
  - [x] **[FE] 도움말 UI** — `KeyHelp` 컴포넌트: 역할 + "발급받기 →"·"문서 →" + "발급 방법"(사전조건·단계) 접기. ResultCard·VaultRow 삽입
  - [x] **[FE] 안전** — 외부 링크 `target=_blank rel=noopener noreferrer`, 자동 이동/전송 없음
- **하위 할일 (B: 딥링크)** — ✅ 완료
  - [x] `issue_url` `{project}` 플레이스홀더를 항목 `project`(또는 meta `gcp_project`)로 치환해 딥링크(`resolveIssueUrl`). GCP KB에 `?project={project}` 추가. **project 가 ID 형태(공백·한글 아님)일 때만** 치환, 아니면 플레이스홀더 쿼리 제거 후 기본 콘솔로 안전 폴백
  - [x] URL 인코딩(`encodeURIComponent`) + **도메인 화이트리스트**(`ALLOWED_HOSTS` = 지식베이스 선언 호스트, https 만) — `isAllowedUrl`. 문서 링크도 동일 통과. `javascript:`·외부 도메인 차단
- **테스트 체크리스트**
  - [x] 🧪 `/knowledge` 도움말 노출(백엔드 `test_knowledge_exposes_guide_help`) · 프론트 레지스트리 흐름(`services.test`)
  - [x] 🧪 `issue_url` 플레이스홀더 치환/폴백·화이트리스트(`services.test`: ID면 치환, 한글라벨/없음이면 기본 콘솔, 외부·비https 거부)
  - [x] ✅ 외부 링크는 `rel=noopener noreferrer`·새 탭, 자동 이동/전송 없음(보안)
  - [x] ✅ 링크 도메인 화이트리스트 — 알려진 콘솔 도메인만 허용(B)
- **추가 후보(선택, 여유 시)**: `usage_snippet`(코드 사용 예시 한 줄, 예: `os.environ['OPENAI_API_KEY']` — `.env` 내보내기와 엮임) · 관련 키 세트 안내("이 서비스는 이런 키들도 있어요", Kakao 4종).
- **범위 밖(스코프 사수)**: 콘솔 자동 로그인·키 자동 발급(OAuth 대행) 등은 하지 않는다 — **안내(링크·설명)까지만**. 실제 발급은 사용자가 공식 콘솔에서 직접.
- **관련**: 보안 등급·유출 대응·상태 연동은 → **GUIDE-2**.

### GUIDE-2 🟡 키 보안 등급·재발급·상태 연동 (GUIDE-1 확장) — ✅ 대부분 완료
- **중요도**: 🟡 Medium(보안 실체) | **스프린트**: GUIDE-1 이후 | **의존성**: GUIDE-1, TRUST-1(검증)·TRUST-2(만료)·VAULT-2(회전)·CORE-2(충돌 카드) | **사이즈**: M
- **배경**: GUIDE-1이 "어디서·어떻게 발급"이라면, GUIDE-2는 **"안전하게 다루고, 유출·만료 시 조치"**다. 같은 서비스라도 **공개 가능 키 vs 절대 노출 금지 키**가 갈리는데(Kakao JS vs REST/Admin, Stripe pk vs sk, Slack bot vs user), 이를 명시해 **유출을 예방**하고, 폐기/재발급 링크로 **사고에 대응**하며, 기존 기능(키 회전·유효성 검증·만료 알림)과 **행동으로 연결**한다.
- **하위 할일**
  - **[Data] KB 보안 필드 추가** (선택, 하위호환)
    - [x] `exposure`: `public` | `secret` — 22종 전부 지정(Kakao JS/Native=public, REST/Admin=secret 등)
    - [x] `impact`: 유출 시 피해 한 줄 — secret 종류에 채움
    - [x] `security_tip`: per-key 하드닝 팁 — GCP(IP/referrer 제한)·AWS(IAM 최소권한)·GitHub(fine-grained·만료)·OpenAI(사용량 한도) 등
    - [~] `revoke_url`: **별도 필드 없이 콘솔(issue_url/console_url) 재사용** — 발급=폐기가 같은 콘솔이라 재사용이 간결. scope_hint 는 security_tip 에 흡수.
  - [x] **[FE] 노출 등급 뱃지** — `ExposureBadge`: `secret`=빨간 "🔒 노출 금지", `public`="공개 가능". ResultCard 헤더·보관함 행(secret)·KeyHelp 에 표시
  - [x] **[FE] "재발급 →" 링크** — 상태 연동에서(아래), `resolveIssueUrl`+화이트리스트(새 탭·noopener)
  - **[연동] 상태 → 액션 연결**
    - [x] TRUST-1 `invalid` → 보관함 검증줄에 **"재발급 →"** (빨간 링크)
    - [ ] TRUST-2 만료 임박/만료 → "재발급 →" (잔여, 여유 시)
    - [x] 값 교체(회전) 모달 → **"먼저 새 키 발급 →"** 링크
  - [x] **[FE] 보안 팁·피해 문구 표시** — `impact`(유출 피해, 빨강)·`security_tip`(💡)를 KeyHelp 에 표시
  - [ ] **[분류 이해 돕기] 신호 충돌 카드 "구분법"** — 잔여. (현재도 충돌 카드가 옵션별 evidence·신호 강약을 이미 보여줌 — 최소 커버됨)
- **테스트 체크리스트**
  - [x] 🧪 `exposure` → 백엔드 `test_knowledge_exposes_security_grade`(admin=secret/js=public) · 프론트 레지스트리 흐름(`services.test`)
  - [x] ✅ 재발급 링크는 새 탭·`rel=noopener noreferrer`, `isAllowedUrl` 화이트리스트(오픈리다이렉트 방지)
  - [x] 🧪 TRUST-1 invalid → 재발급 링크 노출(VaultRow) · 회전 모달 발급 링크
  - [x] ✅ 자동 폐기·자동 재발급은 하지 않음(링크·안내까지만)
- **범위 밖**: 키 자동 폐기·자동 재발급·OAuth 대행 없음 — 안내·링크까지만. 노출 등급은 **보조 신호**이며 최종 판단은 사용자 몫(오탐 시 과신 금지).

---

## EPIC-INTEG — 프론트 ↔ 백엔드 연결 (신설)

> 백로그 원안은 "UI가 CORE를 직접 호출"로 뭉뚱그렸으나, React↔FastAPI 분리 구조에는 실제 **통합 계층**이 존재한다. 프론트(목업)와 백엔드(Stage1)가 각각 생긴 지금이 이걸 잇고 엔드투엔드를 조기 검증할 시점.

### INTEG-1 🟠 프론트 ↔ 백엔드 연결 (엔드투엔드) — ✅ 대부분 완료
- **중요도**: 🟠 High | **스프린트**: S1 말 ~ S2 | **의존성**: CORE-1(✅), UI 골격(✅) | **사이즈**: M | **상태**: ✅ text·URL 연결 완료(/knowledge·dev스크립트 잔여)
- **배경**: 지금 프론트의 분석은 `setTimeout` 목업(`freshResults()`)이고 종류맵(`TYPE_MAP`/`SVC_META`)이 하드코딩돼 있다. 백엔드 `/analyze`·`/knowledge`(포트 8003)로 교체해 실제로 한 번 돌린다.
- **하위 할일**
  - **[FE] API 클라이언트 (`src/api/`)**
    - [x] `POST :8003/analyze` 호출 + 응답→`AnalysisResult` 매핑, 타임아웃(AbortController)·에러 처리 (`client.ts`/`map.ts`)
    - [x] `startAnalyze` 목업→실제 호출 교체. 이미지 단독(텍스트/URL 없음)은 OCR 미구현이라 샘플 목업 유지, 백엔드 미연결 시 목업 폴백 + 안내
    - [ ] `GET :8003/knowledge`로 종류맵 단일화(하드코딩 `TYPE_MAP` 제거 방향) — 후속
  - **[계약] 응답 스키마 정합**
    - [x] 백엔드 `ClassifiedItem` ↔ 프론트 `AnalysisResult` 매핑 확정. 조인 키 = `official_env_name`. conf(high/medium/unknown→high/mid/low), service id→enum, unknown(service=null) 분리 렌더
    - [x] 개발용 실행: 백/프론트 동시 기동 스크립트 `scripts/dev.mjs`(OSS-3에서 완료)
- **테스트 체크리스트**
  - [x] 🧪 `.env` 텍스트 붙여넣기 → 백엔드 분류(OpenAI high 카드 + Kakao unknown 배너) — 계약/CORS 검증
  - [x] ✅ 백엔드 미기동 시 목업 폴백 + 토스트(크래시 없음)
  - [x] ✅ CORS: 프론트(5173/5199) → 백엔드(8003) preflight·POST 정상

---

## EPIC-VAULT — 저장 & 인증

### VAULT-0 ⚪ 레포 스캐폴딩 & OSS 베이스 — ✅ 완료
- **중요도**: 🟠 High | **스프린트**: S1 | **의존성**: 없음 | **사이즈**: S | **상태**: ✅
- **배경**: 첫날 OSS 위생을 깔고 시작(막판에 몰면 라이선스 검증에서 깨짐).
- **하위 할일**
  - [x] `LICENSE`(MIT), `CLAUDE.md`(가드레일), `.gitignore`(`.env`·키파일·SQLite 제외) 배치
  - [x] FastAPI + React 최소 골격, 실행 README (루트/frontend/backend)
  - [x] 모든 새 파일에 SPDX 헤더 (수동 삽입 확인)
- **테스트 체크리스트**
  - [x] ✅ `git status`에 `.env`·`*.sqlite`·`.venv`·`node_modules`가 안 잡힘
  - [ ] ✅ `reuse lint` 통과(헤더 누락 0) — 제출 전 자동 검증으로 확정(OSS-2)

### VAULT-1 🔴 암호화 저장소 — ✅ 코어 완료(엔진+저장소, API/프론트 연결은 VAULT-2)
- **중요도**: 🔴 Critical | **스프린트**: S3 | **의존성**: VAULT-0 | **사이즈**: L | **상태**: ✅ `crypto.py`·`vault_repo.py`, pytest 10개, `cryptography==49.0.0`(감사 통과)
- **배경**: "나만 보기"의 실체. 마스터 비밀번호에서 키를 유도해 값을 암호화 저장. **마스터 비밀번호·복호화 키는 절대 디스크에 평문 저장하지 않는다.**
- **하위 할일**
  - **[Engine] `crypto.py`**
    - [x] Argon2id로 마스터 비밀번호 → 32B 키 유도(솔트·파라미터만 저장, 키는 메모리에만)
    - [x] 값별 AES-256-GCM 암호화(고유 nonce), GCM 태그 무결성·인증 검증(변조/오답 거부)
    - [x] 마스터 비밀번호 변경 시 새 솔트로 검증기+전 항목 재암호화(원자적)
  - **[Storage] `vault_repo.py` (SQLite)**
    - [x] 스키마: `entries(id, service, kind, official_name, label, nonce, ciphertext, created_at, expires_at?)` + `meta`(KDF 파라미터·비밀번호 검증기)
    - [x] 암호문만 저장(평문 값 컬럼 없음). 항목별 `official_name` AAD 바인딩(라벨 스왑 변조 탐지)
- **테스트 체크리스트**
  - [x] 🧪 저장→로드 라운드트립으로 원문 복원
  - [x] 🧪 틀린 마스터 비밀번호 → 복호화 실패(태그 불일치)로 안전하게 거부
  - [x] 🧪 SQLite 파일을 직접 열어도 평문 키가 안 보임(컬럼·바이트 스캔)
  - [x] ✅ 마스터 비밀번호 변경 후에도 기존 항목 정상 복호화, 옛 비밀번호 거부
  - [ ] ⏸ API 엔드포인트(/vault …) + 프론트 목업 → 실제 금고 연결 — VAULT-2(인증 게이트)에서

### VAULT-2 🟠 인증 게이트 — ✅ 완료
- **중요도**: 🟠 High | **스프린트**: S3 | **의존성**: VAULT-1 | **사이즈**: M | **상태**: ✅ 완료 — 백엔드(pytest 16)+프론트 연결+**브라우저 E2E 실검증 통과**
- **배경**: 값 조회·내보내기 전 마스터 비밀번호 인증. 발급 직후 최초 저장 빼고는 항상 인증 필요(사용자 요구사항).
- **하위 할일**
  - [x] 세션 잠금/해제 + 자동 잠금(무활동 타이머) — `vault_session.py VaultService`(메모리 키, clock 주입)
  - [x] 잠금 상태에서는 목록 **메타데이터만** 노출, 값 복호화는 인증 필요 — `/vault/entries`(메타) vs `/vault/entries/{id}/value`(잠금 시 401)
  - [x] 인증 실패 제한(연속 실패 시 백오프 지연 → 429 Retry-After)
  - [x] API: `/vault` status/init/unlock/lock/entries(CRUD)/change-password + 예외→HTTP 매핑
  - [x] 프론트 목업 → 실제 `/vault` 연결: 부팅 상태 라우팅, 설정→init, 잠금화면→실인증(401/429),
    저장→암호화 add, 보관함→서버 목록, 값 공개→복호화 API(잠금 시 재인증), 삭제/메모수정/.env 내보내기
  - [x] **허위 보안표시 해소**: "암호화 저장 준비 중"·"암호화 안 됨" 문구를 실제 상태(AES-256-GCM 암호화)로 교체
  - [x] 브라우저 E2E 실검증: 설정→금고생성→분석(Ollama)→암호화 저장→보관함→값 공개(복호화)→
    잠금(값 401·메타 유지)→틀린 비번 거부→올바른 비번 해제 전 과정 통과(2026-07-05)
- **테스트 체크리스트**
  - [x] 🧪 잠금 상태에서 값 요청 → 거부(VaultLocked/401) + 인증 유도
  - [x] ✅ 자동 잠금 타이머 동작(clock 주입 검증)
  - [x] 🧪 연속 실패 백오프 → RateLimited, 성공 시 리셋

---

## EPIC-UI — 입력 & 조회

### UI-1 🟠 입력 화면 (스크린샷 + URL + 붙여넣기) — ✅ 완료(실데이터 연결)
- **중요도**: 🟠 High | **스프린트**: S1 완료 | **의존성**: CORE-1/2/3 | **사이즈**: M | **상태**: ✅ UI + 실 API(OCR·/analyze) 연결 완료(INTEG-1/CORE-3)
- **배경**: "메모장 대신 여기에 던진다"의 입구. 스크린샷이 1번 무기, URL 보조, 텍스트 붙여넣기 기본.
- **하위 할일**
  - [x] 텍스트 붙여넣기 입력 (UI 완료 — 호출은 INTEG-1에서 실 API로)
  - [x] 이미지 드래그&드롭/붙여넣기 UI (OCR 연결은 CORE-3)
  - [x] URL 입력 필드 (맥락 분류 연결은 CORE-2)
  - [x] 분류 결과 미리보기 카드: 종류·official_name·confidence·신호충돌 해소·수정·확정
- **테스트 체크리스트**
  - [x] ✅ (목업)붙여넣기 → 분류 결과 카드 표시 — 실 API는 INTEG-1
  - [x] ✅ confidence 낮은 항목 "확인 필요" 뱃지

### UI-2 🟠 조회 대시보드 (서비스별 한눈에) — ✅ 완료(실 금고·인증 연결)
- **중요도**: 🟠 High | **스프린트**: S3 | **의존성**: VAULT-1/2 | **사이즈**: M | **상태**: ✅ UI + 실 금고(VAULT-1)·인증(VAULT-2) 연결 완료(브라우저 E2E)
- **배경**: 사용자가 원했던 "한눈에 보고 관리". 서비스 단위 그룹핑 + 연결 관계(같은 워크스페이스 키 묶음).
- **하위 할일**
  - [x] 서비스별 그룹 카드(Notion·Kakao·GCP…) + 키 종류별 행
  - [x] 값 복사 버튼 + 마스킹/공개 토글(4초 후 재마스킹) — 인증 연동은 VAULT-2
  - [x] 검색·필터, 만료 임박 뱃지, 회전 이력, 상세 펼침
  - [x] 항목 편집·삭제(확인 다이얼로그), `.env` 내보내기 모달, 값 교체(회전) 모달, 감사 이력 표시
  - [x] 실 금고(VAULT-1)·인증(VAULT-2) 연결 — 부팅 라우팅·목록·값 복호화·잠금 마스킹·자동잠금(VAULT-2에서 완료, 브라우저 E2E)
- **테스트 체크리스트**
  - [x] ✅ 같은 서비스 키들이 한 그룹으로 묶여 표시
  - [x] ✅ 잠금 상태에서 값 마스킹 유지

---

## EPIC-TRUST — 신뢰 기능 (⚠️ stretch — S4 시간 부족 시 1순위 컷)

### TRUST-1 ✅ 키 유효성 체크 (살아있나?)
- **중요도**: 🟡 Medium(stretch) | **스프린트**: S4 | **의존성**: VAULT-1, CORE-4 | **사이즈**: M
- **배경**: 단순 보관을 넘어서는 한 끗. 만료일을 몰라도 "이 키 죽었어요"는 실제 호출로 알 수 있다(TruffleHog의 verification 발상, 단 코드는 직접 구현).
- **하위 할일**
  - [x] 지식베이스에 서비스별 "검증용 read-only 엔드포인트" 정의 (`verify:` 블록 — OpenAI `/v1/models`, Notion `/v1/users/me`; KB 확장만으로 추가)
  - [x] 사용자 트리거 시 1회 호출 → `active/invalid/unknown/unsupported` 표시 (`POST /vault/entries/{id}/verify`)
  - [x] 검증은 **명시적 실행만**(POST, 자동 주기 호출 없음) · read-only(GET/HEAD)만 허용
  - [x] 새 의존성 0 — httpx(certifi/MPL) 대신 표준 `urllib` 사용으로 permissive-only 유지
- **테스트 체크리스트**
  - [x] 🧪 유효 더미 키(모킹 200) → active, 폐기 키(401) → invalid, 네트워크 오류 → unknown
  - [x] ✅ 값 노출 없이 상태만 갱신(반환 튜플·이력에 키 원문 없음) · 검증도 감사 이력('유효성 검증')에 기록

### TRUST-2 ✅ 만료일 입력 & 임박 알림
- **중요도**: 🟡 Medium(stretch) | **스프린트**: S4 | **의존성**: VAULT-1 | **사이즈**: S
- **배경**: 대부분 생짜 API 키엔 만료 정보가 없으므로 **사용자 입력 기반**으로 처리(JWT류는 exp 자동 파싱 시도).
- **하위 할일**
  - [x] 항목에 `expires_at` 수동 입력 (VaultRow 날짜 인풋 → PATCH 저장)
  - [x] JWT 형태면 `exp` 자동 추출 시도 (`jwtExp()` — 저장 시 자동 채움 + 토스트 안내)
  - [x] 임박(≤14일)·만료 항목 목록 상단 정렬 + 뱃지 강조
- **테스트 체크리스트**
  - [x] 🧪 JWT 입력 → exp 자동 채움 (`format.test.ts` 6케이스, 오탐 없음)
  - [x] ✅ 만료 임박 항목이 상단/뱃지로 강조

---

## EPIC-SYNC — 멀티 기기 (⚠️ stretch / post-MVP)

### SYNC-0 ✅ 암호화 금고 내보내기/가져오기
- **중요도**: 🟡 Medium(stretch) | **스프린트**: S4 | **의존성**: VAULT-1, VAULT-2 | **사이즈**: S
- **배경**: 서버 없이 멀티 기기를 해결하는 최소 단위. 금고 내용물은 전부 암호문이므로, **암호화된 금고 파일 자체**를 내보내 개인 클라우드(Google Drive 등)·USB로 옮기고 다른 기기의 KeyLens에서 가져오면 된다. 여는 열쇠는 여전히 마스터 비밀번호 — 제로 널리지가 유지된다(KeePass + Dropbox 패턴).
- **구현 노트**: 단일 JSON 번들 포맷(`.klvault.json`, `format`/`version` 메타 + base64 KDF·검증기·항목별 nonce/암호문). SQLite 파일 대신 번들을 택해 포맷 버전·검증·병합 제어를 명시화. 병합은 번들 키로 복호화 후 **기존 금고 키로 재암호화**(교체는 암호문 그대로 이식).
- **하위 할일**
  - [x] 금고 파일 내보내기: 단일 암호화 번들(JSON) + 포맷/버전 메타데이터 (`POST /vault/export`)
  - [x] 가져오기: 파일 선택 → 포맷/버전 검증 → 마스터 비밀번호로 복호화 시도 → 성공 시에만 병합/교체 (`POST /vault/import`)
  - [x] 기존 금고와의 관계 선택 UI: "교체" / "병합(중복 official_name은 건너뜀·개수 보고)"
  - [x] 내보내기는 **인증 상태에서만** 가능 · 파일은 전부 암호문("마스터 비밀번호 없이는 못 엶" 안내)
- **테스트 체크리스트**
  - [x] 🧪 내보낸 파일을 새 환경에서 가져오기 → 동일 마스터 비밀번호로 전체 항목 복원 (라운드트립 + 라이브 HTTP)
  - [x] 🧪 틀린 마스터 비밀번호로 가져오기 → 복호화 거부(401), 기존 금고 무손상
  - [x] 🧪 내보낸 파일을 직접 열어도 평문 미노출(JSON 스캔)
  - [x] ✅ 손상된/구버전 파일 가져오기 시 명확한 에러(422, 크래시 금지)

### SYNC-1 ⚪ Google Drive 자동 동기화 (post-MVP — 로드맵 전용, 이번 범위 아님)
- **중요도**: ⚪ Roadmap | **스프린트**: 대회 이후 | **의존성**: SYNC-0 | **사이즈**: M~L
- **배경**: SYNC-0의 수동 파일 이동을 자동화. Google OAuth 로그인 후 **사용자 본인의 Drive appDataFolder**에 암호문 번들을 자동 업로드/다운로드. 우리 서버는 여전히 없음(사용자의 클라우드가 저장소) — 로컬 우선 원칙을 유지하면서 멀티 기기를 얻는 구조. Drive에는 암호문만 올라가므로 계정 유출 시에도 키는 안전(제로 널리지).
- **설계 메모 (착수 시 참고)**
  - OAuth 스코프는 **`drive.appdata`만** 사용(앱 전용 숨김 폴더) — 사용자 드라이브 전체 접근 권한 요구 금지
  - OAuth 클라이언트 미검증 상태 한계(경고 화면, 테스트 사용자 제한) → README에 "본인 클라이언트 ID 발급" 절차 필요
  - 충돌 처리: MVP 수준은 타임스탬프 비교 + "원격이 더 최신, 덮어쓸까요?" 확인 다이얼로그. 자동 병합은 범위 밖
  - 로그인은 "어느 계정의 암호문을 받을지" 식별 용도일 뿐, 복호화 열쇠는 항상 마스터 비밀번호
- **테스트 체크리스트** (착수 시 작성)

---

## EPIC-OSS — 제출물 & 재현성 (코드만큼 채점됨)

### OSS-1 🟠 테스트·에러처리·안정화 — ✅ 완료
- **중요도**: 🟠 High | **스프린트**: S4 | **의존성**: 전체 | **사이즈**: M | **상태**: ✅ backend pytest 96 · frontend 하드닝(build·lint·vitest)
- **하위 할일**
  - [x] 핵심 경로 단위테스트(CORE-1/2, VAULT-1/2) + 분류 정확도 회귀셋(DEMO-1 골든 픽스처)
  - [x] 엣지케이스: 빈·공백·제어문자·구분자폭탄·거대입력(analyze 무크래시 회귀셋) · 깨진 이미지(FileReader onerror + 비이미지 안내) · 잘못된 YAML(파일명 에러 5종) · 약한 비번(백엔드 8자 강제) · OCR 실패(토스트)
  - [x] 사용자 친화 에러 메시지: analyze 4xx(입력 문제)/5xx(서버) 구분, 백엔드 미연결 폴백+안내, 잠금 401 재인증 유도
  - [x] **ErrorBoundary**: 예기치 못한 렌더 오류를 흰 화면 대신 복구 UI로(값·시크릿 미노출)
- **테스트 체크리스트**
  - [x] ✅ 테스트 통과율 + 핵심 경로 커버리지(backend 96 · frontend vitest/build · 브라우저 E2E)
  - [x] ✅ 잘못된 입력에도 크래시 없음(백엔드 회귀셋 + 프론트 onerror/ErrorBoundary)

### OSS-2 🔴 라이선스 셀프 검증 (2차 평가 대비) — ✅ 완료(포털 도구 사전점검만 제출주간)
- **중요도**: 🔴 Critical | **스프린트**: 제출주간 | **의존성**: 전체 | **사이즈**: S | **상태**: ✅ 카피레프트 0 · reuse lint 통과 · SBOM 작성 (2026-07-05, 병렬 에이전트 스캔)
- **배경**: 대회가 **명시적으로 라이선스 충돌을 검증**한다. 제출 전 같은 기준으로 셀프 통과시켜 두는 게 최대 리스크 해소.
- **⚠️ 상시화**: 제출주간에 몰지 말고 **의존성 추가 때마다** 검사한다(`/done`·`/pre-commit` 스킬에 내장). — S1에서 이미 `certifi`(MPL-2.0, httpx 경유) 감지·제거함.
- **하위 할일**
  - [x] `pip-licenses`/`license-checker`로 전체 의존성 라이선스 출력 → **카피레프트 0 확인**. 빌드 CSS 도구가 끌던 MPL-2.0 `lightningcss`는 tailwind 계열을 devDependencies 로 재분류해 배포(런타임) 트리에서 제외.
  - [x] `THIRD-PARTY-NOTICES.md` 완성 — OCR·암호화 + 프론트/백엔드 런타임 배포 의존성 전부 기재.
  - [x] `reuse lint` 통과 — **102/102 파일, Invalid 표현식 0, REUSE 3.3 compliant**. (main.tsx 헤더 추가, index.css 헤더 포맷 수정, `LICENSES/MIT.txt` 추가, 설정·생성 파일과 CJK 오탐 3건은 `.reuse/dep5`로 선언)
  - [ ] ⏳ 대회 포털의 라이선스 검증 도구로 사전 점검 — 제출주간(포털 접근 필요).
  - [x] **[제출물] SBOM(붙임1) 표 작성** — `docs/SBOM.md` 6컬럼(번호/라이브러리명/버전/라이선스/공식URL/사용목적), 직접+전이+모델자산+dev도구 구분.
- **테스트 체크리스트**
  - [x] ✅ 카피레프트 의존성 0건 (백엔드 20종·프론트 production 트리)
  - [x] ✅ 헤더 누락 0건 (reuse lint 102/102)
  - [x] ✅ SBOM 표에 누락 라이브러리 0건(직접 의존성 기준)

### OSS-3 🔴 README + 재현 가능한 빌드 — 🔄 실행 형태·스크립트·README 완료(깨끗VM 검증만 남음)
- **중요도**: 🔴 Critical | **스프린트**: 제출주간 | **의존성**: 전체 | **사이즈**: M
- **배경**: 2차 기능테스트는 **남의 환경에서** 돌린다. "내 컴퓨터에서만 됨"이면 0점.
- **하위 할일**
  - [x] **[결정] 실행 형태**: `docker compose`(결 안 맞음)·PyWebView(안정화 후) 대신 **단일 dev 스크립트** 확정 → `scripts/dev.mjs`(Node, 크로스플랫폼). 백엔드 venv 자동 감지. 실측: 백:8003·프론트:5173 동시 기동 확인.
  - [x] 의존성 버전 고정(requirements.txt / package-lock.json) + `node scripts/dev.mjs` 한 명령 실행.
  - [x] README: 설치(처음 한 번)·실행(한 번에/수동)·빠른 체험·보안 설계 — 실제 상태(암호화 금고)와 일치하게 정합.
  - [x] **배포·온보딩 문서 강화**: `git clone`부터의 전체 절차 + 요구사항 표(버전 확인·설치 링크) + 문제 해결(PowerShell 실행정책·포트충돌·python3 등) + 데이터 저장 위치 안내 + "배포=각자 로컬 실행" 섹션(호스팅 아님) + `CONTRIBUTING.md`(새 서비스 추가법).
  - [ ] ⏳ **깨끗한 환경(새 VM/컨테이너)에서 README대로 처음부터 실행 검증** — 현 세션은 로컬 재현(venv 재생성 → pytest 80 → dev.mjs 200)까지 확인. 새 VM 검증은 제출주간에.
- **테스트 체크리스트**
  - [~] ✅ 로컬에서 문서만 보고 실행 성공(venv 재생성·dev 스크립트). 새 VM은 제출주간.
  - [x] ✅ 데모용 더미 데이터로 즉시 체험 가능(`docs/demo/*.png`)

### OSS-4 🔴 3분 시연영상 + 결과보고서 — 🔄 문서 3종 완료(영상 녹화만 작성자 몫)
- **중요도**: 🔴 Critical | **스프린트**: 제출주간 | **의존성**: 전체 | **사이즈**: M | **상태**: 🔄 보고서·붙임2·스토리보드 작성 완료, 녹화는 작성자 진행
- **배경**: 심사위원의 첫 접점. **magic moment(어지러운 노션 화면 → 깔끔한 라벨 key-value)를 첫 30초**에.
- **하위 할일**
  - [x] 영상 스토리보드: 문제→던지기→자동 분류·매핑→안전 보관/조회, 3분 컷 → `docs/DEMO_SCRIPT.md`(씬별 대본·자막·체크리스트)
  - [ ] ⏳ 화면 녹화·자막 — **작성자 진행**(스토리보드대로 녹화; 실제 키 노출 금지·더미만)
  - [x] 결과보고서: 문제정의·차별점(맥락 분류)·아키텍처·보안설계·오픈소스 전략·한계·재현 → `docs/RESULT_REPORT.md`
  - [x] **[제출물] 붙임2 AI 모델 활용 명세서** → `docs/AI_MODEL_DISCLOSURE.md` — OCR(Tesseract, Apache-2.0) 유형1 외부모델 활용, 추론코드 MIT·저장소 URL, 파인튜닝 없어 데이터셋/가중치 "해당 없음".
  - [ ] ⏳ **[제출물] 붙임2 4번 — 코딩 보조 AI 비율** — 명세서에 기입란 마련. **작성자가 대략치+핵심 로직 이해 확인란을 직접 기입.**
- **테스트 체크리스트**
  - [~] ✅ 영상 ≤ 3분, 첫 30초 핵심 시연 — 스토리보드에 타임라인 반영(녹화 시 확인)
  - [x] ✅ 보고서에 "기존 도구가 못 하는 지점" 1문장 반박 포함(§2)
  - [x] ✅ 붙임2 작성 완료(유형1 체크, 기반 모델·라이선스 기재 누락 없음)

---

## 잘라내기 우선순위 (시간 부족 시)

1. **SYNC-0** (stretch) — 멀티 기기는 로드맵으로 답해도 됨. 가장 먼저 컷.
2. **TRUST-1/2** (stretch) — 없어도 MVP 성립.
3. **CORE-5** `.env` 내보내기 — 데모 비핵심.
4. **UI 폴리시** — 기능 우선, 미관 후순위.

※ SYNC-1(Drive 자동 동기화)은 애초에 이번 범위가 아님 — 결과보고서 로드맵에만 기재.
> 절대 사수: **CORE-2(맥락 분류)**, **VAULT-1(암호화)**, **OSS-2/3/4(라이선스·재현·영상)**. 이 다섯이 무너지면 프로젝트 정체성·채점 모두 흔들린다.