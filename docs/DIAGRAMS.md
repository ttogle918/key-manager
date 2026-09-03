<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->
# KeyLens 설계 다이어그램

> 코드 기준 최신 상태(브랜치 `main`, RUNTIME-1 데스크톱 승인 알림 포함)를 반영한 설계도 모음입니다.
> 기능 하나하나의 설명은 [FEATURES.md](./FEATURES.md), 배경·차별점·한계는 [RESULT_REPORT.md](./RESULT_REPORT.md)를 참고하세요.
> 이 문서는 **구조**(무엇이 무엇과 연결되는가)에 집중합니다 — 다이어그램은 전부 [Mermaid](https://mermaid.js.org/) 코드로,
> GitHub·대부분의 마크다운 뷰어에서 그대로 렌더링됩니다.

## 지금 실제로 되는 기능 (요약)

| 영역 | 상태 | 비고 |
|---|---|---|
| 값 기반 분류 (Stage1) | ✅ 완료 | 10종 서비스, `value_regex` |
| 맥락 기반 분류 (Stage2, 차별점) | ✅ 완료 | 라벨·URL 신호, 충돌 시 사용자 선택 |
| 브라우저 OCR (스크린샷 → 라벨-값) | ✅ 완료 | tesseract.js, 로컬 실행 |
| 암호화 금고 (Argon2id + AES-256-GCM) | ✅ 완료 | SQLite, 평문 컬럼 없음 |
| 인증 게이트 (세션·자동잠금·실패지연) | ✅ 완료 | |
| 감사 이력 · 키 회전 · 값 마스킹 | ✅ 완료 | |
| 키 유효성 검증 (TRUST-1) | ✅ 완료 | 명시적 1회 호출만 |
| 만료일 관리 (TRUST-2) | ✅ 완료 | JWT `exp` 자동 추출 |
| 금고 번들 내보내기/가져오기 (SYNC-0) | ✅ 완료 | 서버 없는 멀티 기기 |
| 발급 도움말 · 보안 등급 (GUIDE-1/2) | ✅ 완료 | 딥링크 화이트리스트 |
| 데스크톱 앱 (PyWebView, exe 패키징) | ✅ 완료 | cx_Freeze |
| **RUNTIME-1 — SDK 백엔드**(`/sdk/*`) | ✅ 완료 | 컬렉션별 허용 디렉토리·승인 대기열·env 값 병합 |
| **RUNTIME-1 — 승인 대기 화면**(`PendingScreen`) | ✅ 완료 | 사이드바 배지·목록·허용/거부 |
| **RUNTIME-1 — 데스크톱 알림**(`notify.py`) | ✅ 완료 | 작업표시줄 깜빡임·OS 토스트·화면 자동 전환(Windows) |
| RUNTIME-1 — `keylens-env` PyPI 패키지 | ⏳ 미착수 | SDK를 실제로 배포할 클라이언트 라이브러리 자체 |
| RUNTIME-1 — 프론트 "디렉토리 등록" 설정 화면 | ⏳ 미착수 | 지금은 승인 대기 목록만 있음(사전 등록 UI 없음) |
| SYNC-2(계정 로그인 서버 동기화) | 📋 로드맵 | 설계만 확정, 이번 범위 아님 |

---

## 1. 아키텍처 개요 (컴포넌트 다이어그램)

브라우저(OCR·UI), 로컬 FastAPI(분류·암호화·SDK 게이트), 선택적 데스크톱 런처(PyWebView + 알림) 세 계층이 전부
한 기기 안에서 협업합니다. 외부 서버는 없습니다.

```mermaid
flowchart LR
  subgraph Browser["브라우저 / SPA (React + TypeScript + Zustand)"]
    IMG[스크린샷] --> OCR["tesseract.js WASM"]
    OCR --> REC["reconstruct — 라벨-값 페어링"]
    REC --> ST[Zustand 스토어]
    URLTXT[URL·텍스트] --> ST
    ST --> PS["PendingScreen"]
  end

  subgraph Backend["FastAPI 로컬 백엔드 (127.0.0.1:8003 / :8765)"]
    AN["POST /analyze"] --> S1["Stage1 값 기반"]
    S1 --> S2["Stage2 맥락 기반"]
    KB[("knowledge/*.yaml\n10종 · 23종류")] --> S1 & S2
    VAPI["/vault/* (15개)"] --> VS["VaultService"]
    VS --> CR["Argon2id + AES-256-GCM"]
    CR --> DB[("SQLite\n암호문만")]
    SDKAPI["/sdk/* (8개)"] --> VS
  end

  subgraph Desktop["데스크톱 런처 (선택 실행, desktop/)"]
    LAUNCH["app.py\npywebview + uvicorn(daemon thread)"]
    NOTIFY["notify.py\n작업표시줄 깜빡임 · OS 토스트 · 화면 전환"]
    LAUNCH -- "VAULT.set_pending_hook(...)" --> NOTIFY
  end

  ST -- JSON --> AN
  ST -- JSON --> VAPI
  ST -- JSON --> SDKAPI
  KB -- "GET /knowledge" --> ST
  VS -. "on_pending 훅" .-> NOTIFY
  NOTIFY -- "evaluate_js(window.__keylensGoPending)" --> PS
  LAUNCH -- "same-origin 정적 서빙(frontend/dist)" --> Browser

  SDKCLIENT(["keylens-env SDK\n(외부 프로세스, 미배포)"]) -. "POST /sdk/env" .-> SDKAPI
```

---

## 2. 유스케이스 다이어그램

Mermaid에는 UML 유스케이스 전용 표기법이 없어, 액터 → 시스템 경계 안 유스케이스로 표현하는 통용 방식을 씁니다.

```mermaid
flowchart LR
  actor(("사용자\n(개인 개발자)"))
  sdkactor(("keylens-env SDK\n(런타임 클라이언트)"))

  subgraph SYS["KeyLens"]
    UC1(["스크린샷·URL·텍스트로\n키 분석"])
    UC2(["신호 충돌 시\n종류 직접 선택"])
    UC3(["분류 결과를\n암호화 저장"])
    UC4(["직접 입력으로\n키/값 저장"])
    UC5(["금고 생성 / 잠금 해제 / 잠금"])
    UC6(["보관함 조회 · 검색 · 필터"])
    UC7(["값 공개(4초) / 복사(30초 자동삭제)"])
    UC8([".env 파일로 내보내기"])
    UC9(["키 유효성 검증"])
    UC10(["만료일 관리 · 임박 알림"])
    UC11(["키 회전(값 교체)"])
    UC12(["금고 번들 내보내기/가져오기"])
    UC13(["발급 도움말 · 보안등급 확인"])
    UC14(["SDK 승인 요청 확인 · 허용/거부"])
    UC15(["런타임에 금고 값 요청"])
  end

  actor --> UC1 --> UC2 --> UC3
  actor --> UC4
  actor --> UC5 --> UC6 --> UC7
  actor --> UC8
  actor --> UC9
  actor --> UC10
  actor --> UC11
  actor --> UC12
  actor --> UC13
  actor --> UC14
  sdkactor --> UC15
  UC15 -. "미등록 디렉토리면\n대기열에 등록" .-> UC14
```

---

## 3. 클래스 다이어그램

### 3.1 백엔드 — 도메인 모델 + 서비스 계층

`vault_repo.py`/`sdk_repo.py`는 클래스가 아니라 `sqlite3.Connection`을 받는 함수 모듈이지만,
`VaultService`가 이들을 감싸는 파사드 역할을 하므로 `<<module>>`로 표시했습니다.

```mermaid
classDiagram
  class VaultService {
    -bytes _key
    -float _last_activity
    -int _fail_count
    -Callable _on_pending
    +init(password)
    +unlock(password)
    +lock()
    +status() dict
    +add_entry(...) int
    +get_value(entry_id, event) str
    +rotate(entry_id, new_value) bool
    +verify_entry(entry_id, spec) tuple
    +export_bundle() dict
    +import_bundle(bundle, password, mode) dict
    +change_password(old, new)
    +sdk_env(project, path) StrDict
    +set_pending_hook(fn)
    +add_project_dir(project, path) dict
    +list_pending() list
    +approve_pending(id) bool
    +deny_pending(id) bool
  }

  class VaultRepoModule {
    <<module: vault_repo.py>>
    +init_vault(conn, password) bytes
    +unlock(conn, password) bytes
    +add_entry(conn, key, ...) int
    +get_value(conn, key, id) str
    +rotate_value(conn, key, id, value) bool
    +export_bundle(conn) dict
    +merge_bundle(conn, existing_key, bundle_key, entries) tuple
  }

  class SdkRepoModule {
    <<module: sdk_repo.py>>
    +add_project_dir(conn, project, path, source) int
    +is_path_approved(conn, project, path) bool
    +is_pending(conn, project, path) bool
    +add_pending_request(conn, project, path) int
    +approve_pending(conn, id) bool
    +entries_for_env(conn, key, project) StrDict
  }

  class KnowledgeBase {
    +list~Service~ services
    +int credential_count
    +find(service_id, kind) Credential
  }
  class Service {
    +str service
    +str display_name
    +str console_url
    +list~str~ steps
    +str disambiguation
    +list~Credential~ credentials
  }
  class Credential {
    +str kind
    +str label
    +list~str~ label_patterns
    +list~str~ url_patterns
    +str value_regex
    +str official_env_name
    +bool expiry_known
    +VerifySpec verify
    +str exposure
    +str issue_url
  }
  class VerifySpec {
    +str method
    +str url
    +str auth
  }
  class ClassifiedItem {
    +str value
    +str service
    +str kind
    +str official_env_name
    +str confidence
    +bool conflict
    +list~ConflictOption~ options
  }

  VaultService --> VaultRepoModule : uses
  VaultService --> SdkRepoModule : uses
  KnowledgeBase "1" *-- "many" Service
  Service "1" *-- "many" Credential
  Credential "0..1" --> "1" VerifySpec
  VaultService ..> KnowledgeBase : verify_entry()가 조회
  ClassifiedItem ..> Credential : Stage1/2가 매칭
```

### 3.2 프론트엔드 — 상태(Zustand 스토어) + 핵심 타입

```mermaid
classDiagram
  class KeylensStore {
    <<Zustand, keylensStore.ts>>
    +Screen screen
    +View view
    +AnalysisResult[] results
    +VaultItem[] vault
    +PendingRequest[] pendingRequests
    +boot()
    +startAnalyze()
    +save(id)
    +reveal(id)
    +copy(text, label)
    +verifyEntry(id)
    +exportVault()
    +importVault(file, password, mode)
    +goPending()
    +loadPending()
    +approvePending(id)
    +denyPending(id)
  }
  class AnalysisResult {
    +string service
    +string typeKey
    +Confidence conf
    +string full
    +bool conflict
    +ConflictOption[] options
    +number[] ocrUncertain
  }
  class VaultItem {
    +string id
    +string service
    +string varName
    +string full
    +string expiresAt
    +VerifyState verify
    +HistoryEntry[] history
  }
  class PendingRequest {
    +number id
    +string project
    +string path
    +string requestedAt
  }
  class ApiClient {
    <<module: api/client.ts>>
    +analyzeApi(req)
    +fetchKnowledge()
    +vaultApi
    +sdkApi
  }

  KeylensStore --> AnalysisResult
  KeylensStore --> VaultItem
  KeylensStore --> PendingRequest
  KeylensStore --> ApiClient : 전부 이 클라이언트로 호출
```

---

## 4. 데이터 모델 (SQLite 스키마, `vault.db`)

암호화 값 자체는 `nonce`/`ciphertext` BLOB로만 존재하고, 평문 값 컬럼은 어떤 테이블에도 없습니다.

```mermaid
erDiagram
  ENTRIES ||--o{ ACCESS_LOG : "감사 이력"

  META {
    int id PK "항상 1행"
    blob kdf_salt
    int kdf_time
    int kdf_memory
    int kdf_lanes
    blob verifier_nonce
    blob verifier_ct
    text created_at
  }
  ENTRIES {
    int id PK
    text service
    text kind
    text official_name
    text label
    text project
    text memo
    blob nonce
    blob ciphertext "평문 값 컬럼 없음"
    text created_at
    text expires_at
  }
  ACCESS_LOG {
    int id PK
    int entry_id FK
    text event "register/reveal/copy/export/rotate/verify/sdk_fetch"
    text at
  }
  SDK_PROJECT_DIRS {
    int id PK
    text project
    text path
    text path_norm "매칭용 정규화 값"
    text source "manual | approved"
    text created_at
  }
  SDK_PENDING_REQUESTS {
    int id PK
    text project
    text path
    text path_norm
    text requested_at
  }
```

> `SDK_PROJECT_DIRS`/`SDK_PENDING_REQUESTS`는 `ENTRIES`와 외래키로 묶이지 않습니다 — `project` 문자열로만
> 느슨하게 연결됩니다(`sdk_env()`가 조회 시점에 두 값을 나란히 읽어 병합). `UNIQUE(project, path_norm)`으로
> 같은 (컬렉션, 경로) 조합의 중복 등록/중복 대기를 막습니다.

---

## 5. 시퀀스 다이어그램 (핵심 흐름)

### 5.1 스크린샷 → 분류 → 저장

```mermaid
sequenceDiagram
  actor U as 사용자
  participant FE as 프론트(SPA)
  participant OCR as tesseract.js(브라우저)
  participant BE as FastAPI(/analyze)
  participant KB as 지식베이스

  U->>FE: 스크린샷 드롭/붙여넣기
  FE->>OCR: OCR 실행 (WASM, 로컬)
  OCR-->>FE: 라벨-값 페어 텍스트(bbox 보존)
  FE->>BE: POST /analyze {text, url}
  BE->>KB: Stage1 — value_regex 매치 시도
  alt 값으로 확정 가능
    KB-->>BE: service/kind 확정(high)
  else 값만으로 애매
    BE->>KB: Stage2 — 라벨·URL 신호 수집
    KB-->>BE: high/medium/conflict/unknown
  end
  BE-->>FE: ClassifiedItem[]
  FE-->>U: 결과 카드(신뢰도 뱃지·충돌 해소 UI·도움말)
  U->>FE: 종류 확정 후 저장
  FE->>BE: POST /vault/entries
  BE-->>FE: 저장 완료(Argon2id 키로 AES-256-GCM 암호화됨)
```

### 5.2 잠금 해제(인증)

```mermaid
sequenceDiagram
  actor U as 사용자
  participant FE as 프론트
  participant VS as VaultService(메모리)
  participant DB as SQLite(vault.db)

  U->>FE: 마스터 비밀번호 입력
  FE->>VS: POST /vault/unlock
  VS->>VS: Argon2id(pw, salt) → key
  VS->>DB: 검증기 암호문 읽기 → AES-GCM 복호화 시도
  alt 태그 일치
    VS-->>FE: 200 unlocked(키는 프로세스 메모리에만)
    FE-->>U: 보관함 진입, 값은 클릭 시 4초만 공개
  else 불일치
    VS-->>FE: 401(+연속 실패 시 지수 백오프 429)
    FE-->>U: "비밀번호가 올바르지 않습니다"
  end
```

### 5.3 RUNTIME-1 — SDK 승인 요청 → 데스크톱 알림 → 허용/거부

이번에 새로 구현된 흐름입니다. 알림 작업은 데몬 스레드에서 비동기로 실행되어, `evaluate_js`가 느려도
SDK 요청(`POST /sdk/env`) 자체는 즉시 응답합니다.

```mermaid
sequenceDiagram
    actor U as 사용자
    participant SDK as keylens-env SDK(외부 프로세스)
    participant BE as 백엔드(VaultService.sdk_env)
    participant DT as desktop/notify.py
    participant FE as 프론트(SPA, PendingScreen)

    SDK->>BE: POST /sdk/env {project, path}
    alt 미등록 경로(최초 요청)
        BE->>BE: sdk_repo.add_pending_request() (idempotent)
        BE->>DT: on_pending(project, path) 훅 발화
        DT->>DT: threading.Thread(daemon=True)로 즉시 위임 후 반환
        BE-->>SDK: 403 SdkApprovalPending
        par 데몬 스레드 위에서, 전부 best-effort(예외 흡수)
            DT->>DT: 작업표시줄 아이콘 깜빡임(Windows, FindWindowW+FlashWindowEx)
            DT->>DT: OS 토스트 표시(plyer)
            DT->>FE: evaluate_js("window.__keylensGoPending()")
        end
        FE-->>U: 승인 대기 화면으로 자동 전환
        U->>FE: "허용" 또는 "거부" 클릭
        FE->>BE: POST /sdk/pending/{id}/approve 또는 /deny
        BE-->>FE: 200 OK → 목록 재조회
    else 이미 승인된 경로
        BE->>BE: entries_for_env() — 전역+컬렉션 키 복호화 병합(컬렉션이 override)
        BE->>BE: access_log에 'sdk_fetch' 기록
        BE-->>SDK: 200 {values: {...}}
    end
```

### 5.4 금고 번들 내보내기/가져오기 (SYNC-0)

```mermaid
flowchart LR
  F[".klvault.json"] --> P{형식·버전 검증}
  P -- 실패 --> E422["422 명확한 에러"]
  P -- 통과 --> K["번들 KDF로 키 유도 → 검증기 복호화"]
  K -- 오답 --> E401["401 — 기존 금고 무손상"]
  K -- 성공 --> M{모드}
  M -- 교체 --> R["암호문 그대로 이식"]
  M -- 병합 --> G["복호화 → 기존 키로 재암호화, 중복 건너뜀"]
  R & G --> DB[("vault.db")]
```

---

## 6. 상태 다이어그램

### 6.1 금고 세션

```mermaid
stateDiagram-v2
  [*] --> Uninitialized
  Uninitialized --> Unlocked: init(비밀번호 8자+)
  Locked --> Unlocked: unlock(정답)
  Locked --> Backoff: 연속 실패 초과
  Backoff --> Locked: Retry-After 경과
  Unlocked --> Locked: lock / 자동잠금(무활동)
  Unlocked --> Locked: 비밀번호 변경(재인증 요구)
```

### 6.2 SDK 승인 요청 (RUNTIME-1)

```mermaid
stateDiagram-v2
  [*] --> Unregistered
  Unregistered --> Pending: POST /sdk/env(미승인 경로, 최초 요청)
  Pending --> Pending: 동일 경로 재요청(훅 재발화 없음 — idempotent)
  Pending --> Approved: POST /sdk/pending/{id}/approve
  Pending --> Denied: POST /sdk/pending/{id}/deny
  Denied --> Unregistered: 대기열에서 삭제(재요청 시 다시 Pending)
  Approved --> [*]: sdk_project_dirs에 등록(source=approved)
  Approved --> Approved: 이후 같은 경로 요청은 즉시 200
```

---

## 참고

- 이 문서의 다이어그램은 브랜치 `main`(RUNTIME-1 데스크톱 알림 병합 시점) 코드를 기준으로 손으로 맞춘 것입니다 —
  자동 생성이 아니므로 코드가 바뀌면 이 문서도 함께 갱신해야 합니다.
- 값 기반/맥락 기반 분류 알고리즘 자체의 세부 흐름도(Stage1/Stage2 판정 트리)는 [FEATURES.md](./FEATURES.md#1-분류매핑-엔진)에 더 상세히 있습니다 — 이 문서와 중복되지 않게 링크만 겁니다.
