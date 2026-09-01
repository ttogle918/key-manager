<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# 변경 이력 (Changelog)

이 프로젝트의 주요 변경을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를,
버전은 [유의적 버전(SemVer)](https://semver.org/lang/ko/)을 따릅니다.

## [Unreleased]

### Added (기능)
- **컬렉션 목록 조회(`keylens-env`)**: `keylens_env.collections()` 와 CLI
  `keylens-env collections`(= `python -m keylens_env collections`). 어떤 키 묶음을 쓸 수
  있는지 이름·개수만 보여준다(**값은 출력하지 않는다**). 진단용 `keylens-env where` 도 추가.
- **KeyLens 주소 자동 탐색(`keylens-env`)**: `KEYLENS_BASE_URL` 없이도 데스크톱 포트(8765)와
  개발 포트(8003)를 `/health`로 확인해 **KeyLens가 응답하는 쪽**에 자동으로 붙는다.
  환경변수를 지정하면 탐색 없이 그 주소를 그대로 쓴다.
- **`load_env(override=False)`**: 이미 설정된 환경변수를 보존하는 선택지(python-dotenv와 동일한
  동작). 기본값은 기존과 같은 `True`. `load_env()` 가 실제로 주입한 `{이름: 값}` 을 반환한다.
- `.keylens.toml` 의 `collection` 키(기존 `project` 키도 계속 동작).
- **`.env` 가져오기**: `.env` 파일을 드롭하면 변수 전체를 표로 보여주고 컬렉션 하나로 일괄 저장합니다.
  원본 변수명을 그대로 유지하며(지식베이스 공식 이름은 "제안"으로만 노출), 분류가 안 되는 줄
  (`DB_HOST` 등)도 함께 가져옵니다. 이름·값은 더블클릭으로 편집할 수 있고, 보관함에서 값을
  더블클릭하면 기존 회전 모달이 열립니다. 설계: [`docs/superpowers/specs/2026-08-30-env-import-design.md`](docs/superpowers/specs/2026-08-30-env-import-design.md)

### Fixed (버그)
> 상세 재현·판단 근거는 [`docs/memo/2026-08-29-runtime1-e2e-bug-audit.md`](docs/memo/2026-08-29-runtime1-e2e-bug-audit.md).

- **한글 Windows 콘솔에서 에러 메시지 출력 시 크래시**: 모든 SDK 에러 메시지에 들어 있던
  em dash(U+2014)가 cp949로 인코딩되지 않아, README 예시대로 `print(e)` 하면
  `UnicodeEncodeError` 로 죽었다. 하필 신규 사용자가 가장 먼저 만나는 승인 대기 에러였다.
  메시지 문자열 전체를 검사하는 회귀 테스트(`test_messages.py`) 추가.
- **빈 컬렉션을 조용히 성공 처리하던 문제**: 주입할 변수가 0개여도 성공한 척해서 한참 뒤
  엉뚱한 자리에서 `KeyError` 로 터졌다. 이제 `KeylensEmptyCollectionError` 로 즉시 알린다
  (프로젝트를 지정하지 않고 저장한 키가 등록일 이름으로 묶이는 것이 흔한 원인).
- **`KeylensEnvError` 밖으로 새던 원시 예외**: 해당 포트에 KeyLens가 아닌 다른 프로그램이
  떠 있으면 `JSONDecodeError`, 응답 형식이 다르면 `KeyError('values')` 가 그대로 노출됐다.
  전부 `KeylensServerError` 로 정규화.
- **`.keylens.toml` 인코딩**: Windows 메모장의 'UTF-8'(BOM) 저장분이 "TOML 형식이 아니에요"로
  실패하고, '유니코드'(UTF-16) 저장분은 원시 `UnicodeDecodeError` 를 던졌다.
- **동시 요청 시 500**: 같은 디렉토리에서 여러 프로세스가 동시에 `load_env()` 를 호출하면
  `UNIQUE` 제약 위반(`IntegrityError`)으로 500이 났다. `ON CONFLICT DO NOTHING` 으로 수정.
- **승인 대기 뱃지가 자동 갱신되지 않던 문제**: SDK 요청은 앱 밖에서 오는데 폴링이 없어
  뱃지가 0으로 남았다(특히 dev 모드는 OS 알림도 없어 알 방법이 아예 없었다). 5초 폴링 추가.

### Security (보안)
- **SDK 승인 게이트 우회 차단**: 디렉토리 등록(`POST /sdk/projects/{p}/directories`)과 대기 요청
  승인(`POST /sdk/pending/{id}/approve`)이 잠금 상태에서도 인증 없이 통과해, 임의의 로컬
  프로세스가 자기 디렉토리를 스스로 허용 목록에 넣거나 자기 요청을 스스로 승인한 뒤 사용자가
  다음번 잠금을 해제하는 순간 값을 받아갈 수 있었다. 이제 **권한을 넓히는 작업은 잠금 해제를
  요구**한다(권한을 좁히는 등록 해제·거부와 단순 조회는 잠긴 상태에서도 가능).

### Changed (변경)
- **용어 통일 — 키 묶음은 "컬렉션"**: 앱 화면·문서·SDK에서 모두 **컬렉션(collection)**으로 부릅니다
  (예: "프로젝트 접근" → **"컬렉션 접근"**). 이 시스템에는 *키 묶음*과 *그 묶음을 쓸 수 있는 허용
  디렉토리 목록*이 1:N으로 따로 있는데, 사람들이 "프로젝트"라고 생각하는 건 후자(레포 디렉토리)라
  앞의 것을 "프로젝트"라 부르면 헷갈렸습니다. 벡터스토어가 네임스페이스를 컬렉션으로 나누는 것과
  같은 개념입니다. 판단 근거는
  [`docs/memo/2026-08-29-runtime1-e2e-bug-audit.md`](docs/memo/2026-08-29-runtime1-e2e-bug-audit.md)의
  "용어 결정" 절 참고.
  - **호환성에 영향 없음**: HTTP 필드명·엔드포인트 경로(`/sdk/projects`, `{"project": ...}`)와 DB
    컬럼은 `project` 그대로입니다. `keylens-env`가 다른 레포에 버전 고정으로 설치되므로 와이어
    포맷을 바꾸면 버전 스큐가 나기 때문입니다. `.keylens.toml`의 `project` 키와
    `load_env(project=...)`도 계속 동작합니다.
  - 과거 기록(`CHANGELOG` 0.3.0 이전 항목, `docs/BACKLOG.md`)과 대회 제출 문서
    (`docs/RESULT_REPORT*.md`)는 당시 표기를 유지합니다.
- `README.md` 주요 기능에 런타임 키 주입 SDK(`keylens-env`) 항목 추가 — 구현이 끝난 기능인데
  메인 README에서 빠져 있었습니다.
- `keylens-env` 버전 0.1.0 → 0.2.0. 주소 결정 책임이 `load_env()` 에서 `client.resolve_base_url()`
  로 이동했다(포트 자동 탐색 도입에 따른 정리).
- `keylens-env` 문서에 **자동 잠금 주의** 절 추가: 금고는 무활동 5분이면 자동으로 잠기고,
  SDK 조회는 이 타이머를 갱신하지 않는다(자리 비움 보호 — 의도된 설계). 길게 도는 작업은
  `KEYLENS_AUTOLOCK_SECONDS` 로 조정. `KeylensLockedError` 메시지에도 같은 안내를 넣었다.

## [0.3.0] - 2026-08-27

### Added (기능)
- **화면 설명("이 화면 설명해줘")**: 스크린샷 전체를 박스+라벨 오버레이로 설명. 지식베이스에
  있는 서비스는 즉시 라벨링하고, 모르는 영역은 사용자가 이미 실행 중인 **로컬 Ollama**에게
  짧은 설명 + 서비스명 추측을 요청한다(옵트인, `OLLAMA_MODEL` 없으면 버튼 자체가 안 보임).
- **Tavily 검색 확인 + 로컬 발견 캐시(화면 설명 2·3단계, 옵트인)**: `TAVILY_API_KEY`를 설정하면
  Ollama의 서비스명 추측을 웹 검색으로 재검증해 `ai_verified` 등급 + 공식 문서 링크를 붙인다
  (도메인 제한 없음 — 검색 결과가 실제로 맞는지는 다시 Ollama가 판단). 사용자가 화면에서
  승인한 추정만 로컬 캐시(`local_discoveries.yaml`, git 추적 안 함)에 남아 다음번엔 재검색
  없이 재사용된다.
- **보관함 프로젝트별 그룹핑**: 서비스별 목록 대신 프로젝트별 아코디언으로 재구성, 서비스
  로고 태그로 다중 필터링(simple-icons, CC0-1.0).
- **금고 완전 초기화**: 사이드바에서 마스터 비밀번호 재확인 후 저장된 모든 자격증명·감사
  이력·프로젝트 접근 승인 기록을 완전히 삭제(공용/교육용 PC 시나리오).
- **이메일 릴레이 동기화(SYNC-2)**: 계정·DB 없이 SMTP로만 암호화 금고 번들을 목적지 이메일로
  전달(`manager-relay/`, 독립 배포·옵트인).
- 분석 결과 요약을 MUI DataGrid로 표시.

### Changed (변경)
- **스크린샷 OCR을 백엔드 RapidOCR로 이전(CORE-3)**: 브라우저 `tesseract.js`는 한글 단일 글자
  라벨 오독 문제가 있어, 백엔드에서 한국어 PP-OCRv5 인식 모델로 정확도를 개선했다. 이미지는
  여전히 로컬(127.0.0.1)에서만 처리된다.
- SQLite 삭제된 행이 `VACUUM` 전까지 디스크에 포렌식 복구 가능하게 남던 문제를
  `PRAGMA secure_delete` + `VACUUM`으로 보완.

### Security (보안)
- 화면 설명 파이프라인에서 로컬 모델이 값(시크릿)을 서비스명으로 잘못 추측해도 Tavily 검색
  쿼리로 내보내지 않도록 검증 로직 추가.
- 로컬 발견 캐시의 값-토큰 정규화 규칙을 보강해, 서로 다른 라벨이 동일 패턴으로 뭉개지거나
  일부 시크릿이 평문으로 캐시 파일에 남던 문제를 수정.

## [0.2.0] - 2026-08-10

### Added (기능)
- **keylens-env**: `.env` 파일 없이 실행 중인 KeyLens 금고에서 값을 읽어오는 런타임 SDK
  (`pip install "git+...#subdirectory=keylens-env"`, 새 런타임 의존성 없음).
- **프로젝트 접근 관리**: 프로젝트별 허용 디렉토리 등록, 미등록 디렉토리의 최초 요청 시
  승인 팝업(작업표시줄 깜빡임 + OS 토스트), SDK 조회도 감사 이력에 기록.

### Fixed (수정)
- 개발 모드에서 보관함 항목 삭제·메모/만료일 수정이 CORS 프리플라이트 거부로 동작하지
  않던 문제 수정.

## [0.1.1] - 2026-07-31

### Added (기능)
- **직접 입력 탭**: 새 자격증명 분석 화면에 "직접 입력" 모드 추가. `NAME=VALUE` 붙여넣고
  Enter를 누르면 이름·값 두 칸으로 즉시 분리되고, 지식베이스와 정확히 일치하는 이름이면
  서비스·노출등급을 참고로 보여준다. 이름 칸은 cmd 스타일 Tab 자동완성(고스트 텍스트 +
  후보 순환)을 지원하고, 값을 채우면 새 행이 자동으로 추가된다.

### Fixed (수정)
- 자동 분류 결과가 "값만으로 판별 불가"만 있고 정상 결과가 하나도 없을 때 뒤로 갈 방법이
  없던 문제 — 해당 카드에 "새로 분석" 버튼을 추가하고, 사이드바 홈 탭(분석·입력)을 눌러도
  항상 빠져나올 수 있게 했다.

## [0.1.0] - 2026-07-30

첫 데스크톱 exe 릴리스. 아래는 지금까지 축적된 기능·변경 요약입니다.

### Added (기능)
- **분류 엔진**: 값 기반(Stage1)·**맥락 기반(Stage2, 차별점)** 2단계 분류 — 라벨·URL 신호로
  같은 형식의 애매한 키(Notion UUID류)를 판별, 신호 충돌 시 단정 없이 "확인 필요".
- **브라우저 OCR(CORE-3)**: tesseract.js로 스크린샷 → 라벨-값 페어링(이미지가 기기를 떠나지 않음),
  값 전용 정밀 재인식(bbox 크롭 + PSM + charset) + 신뢰도 플래깅.
- **암호화 금고(VAULT-1/2)**: Argon2id 키 유도 + 항목별 AES-256-GCM, SQLite에 암호문만 저장.
  세션 인증·자동 잠금·연속 실패 지연·감사 이력·키 회전(값 교체).
- **지식베이스**: 서비스별 키 종류·라벨·URL·변수명을 YAML로 선언(현재 9종:
  Notion·Kakao·GCP·OpenAI·Ollama·GitHub·AWS·Slack·Stripe). **YAML 하나로 백엔드·프론트 자동 반영**.
- **TRUST-1**: 사용자 트리거 시 서비스 read-only 엔드포인트로 1회 호출해 키 유효성(active/invalid/unknown) 확인.
- **TRUST-2**: 만료일 수동 입력 + JWT `exp` 자동 추출 + 임박 항목 상단 정렬.
- **SYNC-0**: 암호화 금고 번들 내보내기/가져오기(교체·병합) — 서버 없는 멀티 기기(제로 널리지).
- **CORE-5**: `.env` 내보내기(복사·다운로드·그룹별).
- **데스크톱 앱**: PyWebView 네이티브 창(`desktop/app.py`) + cx_Freeze 단일 실행 파일 패키징.
- **제출물**: 결과보고서·SBOM(붙임1)·AI 모델 활용 명세서(붙임2)·데모 스토리보드.

### Changed (변경)
- 프론트 서비스 종류맵을 하드코딩에서 **`/knowledge` 런타임 동적 구성**으로 전환(확장성 실체화).
- 의존성 상향: `fastapi` 0.115.6→0.139.0, `starlette` 0.41.3→1.3.1, `pytest` 8.3.4→9.0.3.

### Fixed (수정)
- OCR 값 재구성(구두점 분리 토큰 재결합), 프론트 에러 처리 하드닝(ErrorBoundary·친절 메시지),
  엣지 입력 무크래시, 허위 보안 표시 제거.

### Security (보안)
- 유출됐던 실제 테스트 키를 히스토리에서 완전 제거하고 `data/` 를 `.gitignore` 에 추가.
- 라이선스 카피레프트 0건(reuse lint 통과·SBOM), 의존성 취약점(SCA) 전 영역 0건(pip-audit·npm audit).
- 마스킹 노출 축소·감사 이력·잠금 정책 등 [SECURITY_REVIEW.md](./SECURITY_REVIEW.md) 항목 해소.

[Unreleased]: https://github.com/ttogle918/key-manager/compare/v0.3.0...main
[0.3.0]: https://github.com/ttogle918/key-manager/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/ttogle918/key-manager/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/ttogle918/key-manager/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/ttogle918/key-manager/releases/tag/v0.1.0
