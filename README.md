<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# KeyLens

> 스크린샷이나 URL을 던지면 "이건 Notion API 키, 이건 database ID"처럼 **맥락으로 정체를 가려** 공식 환경변수명에 매핑하고, 로컬에 암호화해 나만 볼 수 있게 보관하는 개인 개발자용 자격증명 관리 도구.

## 왜 만들었나

API 연동을 하다 보면 키·토큰·ID가 끝없이 쌓입니다. 이것들은 보통 메모장이나 이름 없는 텍스트 파일에 흩어지고, 두 가지 문제를 낳습니다.

1. **이게 무슨 키인지 모른다.** 노션의 `database_id` · `data_source_id` · `page_id`는 전부 같은 32자리 UUID라 값만 봐서는 구분이 불가능합니다. 카카오는 REST/JavaScript/Admin/Native 키가 한 화면에 비슷한 모습으로 나열되고, GCP는 API 키·서비스 계정 JSON·OAuth 클라이언트가 뒤섞입니다. 기존 시크릿 스캐너(정규식 기반)는 정확히 이 지점에서 "여러 후보 가능"이라며 손을 듭니다.
2. **안전하게 보관할 곳이 없다.** 평문 메모는 유출에 취약하고, 정작 필요할 때 어떤 값이 무엇이었는지 다시 헷갈립니다.

KeyLens는 값 자체가 아니라 **출처의 맥락**(스크린샷 속 라벨, URL 구조)을 분류 신호로 사용해 이 사각지대를 해결합니다.

## 주요 기능

- **다양한 입력**: 콘솔 화면 스크린샷 붙여넣기, URL, 텍스트 붙여넣기
- **2단계 분류 엔진**
  - *Stage 1 (값 기반)*: `sk-`(OpenAI), `ghp_`(GitHub), `AKIA`(AWS) 등 접두사가 명확한 키를 정규식으로 즉시 식별
  - *Stage 2 (맥락 기반)*: 값만으로 애매한 키를 OCR로 읽은 주변 라벨("Database ID", "Internal Integration Secret")과 URL 구조로 판별. 신호가 충돌하면 단정하지 않고 "확인 필요"로 표시
- **공식 변수명 매핑**: 분류 결과를 `NOTION_DATABASE_ID`, `KAKAO_REST_API_KEY` 같은 표준 환경변수명으로 자동 정리
- **암호화 보관**: 마스터 비밀번호 기반(Argon2id + AES-256-GCM). 디스크에는 암호문만 저장
- **조회 대시보드**: 서비스별 그룹으로 한눈에 보고, 인증 후 복사·편집·삭제. 잠금 상태에서는 값 마스킹
- **확장 가능한 지식베이스**: 서비스별 키 종류·라벨·URL 패턴·변수명이 YAML로 선언되어 있어, YAML 파일 하나 추가로 새 서비스 지원 (코드 수정 불필요)

## 아키텍처

```
[ React + TypeScript 프론트엔드 ]  ←→  [ FastAPI 로컬 백엔드 ]
                                          ├─ OCR (Tesseract)
                                          ├─ 분류 엔진 (Stage1 값 기반 / Stage2 맥락 기반)
                                          ├─ 지식베이스 로더 (knowledge/*.yaml)
                                          ├─ 암호화 (Argon2id + AES-256-GCM)
                                          └─ 저장소 (SQLite — 암호문만 저장)
```

**로컬 우선(local-first)**: 외부 서버·클라우드가 없습니다. 모든 데이터는 사용자 기기에만 존재하며 네트워크로 전송되지 않습니다.

## 설치 및 실행

### 요구 사항

- Python 3.11+
- Node.js 20+
- Tesseract OCR (스크린샷 분류 기능 사용 시)
  - Windows: [UB Mannheim 빌드](https://github.com/UB-Mannheim/tesseract/wiki) 설치 후 PATH 등록
  - macOS: `brew install tesseract tesseract-lang`
  - Ubuntu: `sudo apt install tesseract-ocr tesseract-ocr-kor`

### 백엔드

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --port 8003
```

### 프론트엔드

```bash
cd frontend
npm ci
npm run dev
```

브라우저에서 `http://localhost:5173` 접속 → 최초 실행 시 마스터 비밀번호를 설정하면 금고가 생성됩니다.

### 빠른 체험

1. 노션 통합 설정 화면(또는 저장소의 데모 이미지 `docs/demo/`)을 캡처해 입력 화면에 붙여넣기
2. 값과 라벨이 자동 분류되어 `NOTION_API_KEY`, `NOTION_DATABASE_ID` 등으로 매핑된 카드 확인
3. 확정 후 마스터 비밀번호로 암호화 저장 → 대시보드에서 서비스별로 조회

> ⚠️ 체험 시에도 실제 발급 키 대신 더미 값 사용을 권장합니다. 데모·문서의 모든 예시는 명백한 가짜 값(`sk-xxxxxxxx` 등)입니다.

## 보안 설계

- **키 유도**: 마스터 비밀번호 → Argon2id로 암호화 키 유도. 솔트만 저장하며 유도된 키는 메모리에만 존재, 잠금 시 폐기
- **암호화**: 항목별 AES-256-GCM(인증 암호화), 매 암호화마다 고유 nonce. 무결성 태그로 변조 탐지
- **저장**: SQLite에는 암호문·nonce·메타데이터만 저장 — 평문 값 컬럼 자체가 없음
- **접근 통제**: 조회·복사·내보내기 전 인증 필수, 일정 시간 후 자동 잠금, 연속 인증 실패 시 지연

**방어 범위 밖(한계)**: 이미 장악된 호스트(키로거, 메모리 덤프), 약한 마스터 비밀번호. 이 도구는 분실·도난 기기의 디스크 접근, 파일 유출, 저장소 직접 열람으로부터 보호합니다.

## 새 서비스 추가하기

`knowledge/` 디렉토리에 YAML 하나를 추가하면 됩니다.

```yaml
service: example
display_name: Example Service
credentials:
  - kind: api_key
    label_patterns: ["Secret key", "시크릿 키"]
    url_patterns: []
    value_regex: "^ex_[A-Za-z0-9]{24,}$"   # 접두사가 명확할 때만
    official_env_name: EXAMPLE_API_KEY
    expiry_known: false
```

자세한 절차는 `CONTRIBUTING.md`를 참고하세요. 기여 환영합니다.

## 로드맵

- **암호화 금고 내보내기/가져오기**: 암호문 번들 파일을 통째로 내보내 개인 클라우드·USB로 옮기고 다른 기기에서 마스터 비밀번호로 열기 — 서버 없는 멀티 기기
- **Google Drive 제로 널리지 동기화**: 사용자 본인의 Drive 앱 전용 폴더(appDataFolder)에 암호문만 자동 업로드/다운로드. 복호화 열쇠는 항상 로컬의 마스터 비밀번호이며, 자체 서버는 만들지 않음
- **DOM 기반 자동 캡처**(브라우저 확장): 권한 모델·프라이버시 설계 검증 후 도입
- 더 많은 서비스 지식베이스, 런타임 주입(SDK)

## 라이선스

MIT — [LICENSE](./LICENSE) 참조.
서드파티 의존성 및 참고 출처는 [THIRD-PARTY-NOTICES.md](./THIRD-PARTY-NOTICES.md)에 정리되어 있습니다.
