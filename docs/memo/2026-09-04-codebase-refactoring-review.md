<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# 코드베이스 이해 및 리팩토링 검토 (2026-09-04)

> 대상: 저장소 전체(백엔드·프론트·데스크톱·SDK·릴레이). 기준 커밋 `a11a8e2`.
> 관점: 막 합류한 시니어 엔지니어. 먼저 **아키텍처와 데이터 흐름을 이해하고**, 그 다음
> 구조적 문제·중복·성능·유지보수 위험을 찾는다.
> 전제: **기능은 변하지 않는다.** 아래 제안은 전부 동작 보존 리팩토링이다.
> 방법: 인상이 아니라 **측정**했다. 줄 수·중복 횟수·의존성 참조·연결 비용을 직접 셌다.

---

## 1. 아키텍처 요약

### 1.1 배포 단위 5개

| 단위 | 역할 | 규모 |
|------|------|------|
| `backend/app` | FastAPI. 분류·금고·SDK 게이트. `127.0.0.1` 바인딩 | 3,694줄 / 20파일 |
| `frontend/src` | React SPA. 백엔드와 same-origin | 8,262줄 / 48파일 |
| `desktop/` | pywebview 셸. SPA·백엔드를 한 프로세스로 묶어 exe 로 패키징 | 973줄 / 9파일 |
| `keylens-env/src` | dotenv 대체 런타임 SDK | 471줄 / 5파일 |
| `manager-relay/app` | **독립 배포** SMTP 릴레이. 계정·DB 없음 | 526줄 / 6파일 |

테스트는 `backend/tests` 4,195줄(29파일)로 백엔드 소스보다 크다 - 좋은 신호다.

### 1.2 데이터 흐름

```
입력 ──┬─ 스크린샷 ─→ RapidOCR(백엔드) ─┐
       ├─ URL/텍스트 ───────────────────┤
       └─ .env 파일 ─→ 프론트 직접 파싱 ─┤   (값 기준 중복제거를 피하려 프론트에서 파싱)
                                          ▼
                          분류 Stage1(값 정규식) → Stage2(맥락)
                                          │
                                knowledge/*.yaml (10종)
                                          ▼
                      금고: Argon2id → AES-256-GCM(AAD=변수명)
                                  SQLite 에는 암호문만
                                          ▼
출력 ──┬─ .env 내보내기
       ├─ keylens-env SDK (디렉토리 승인 게이트)
       └─ 이메일 번들 (릴레이 3단계 발송)
```

### 1.3 이 설계에서 잘 된 것

- **지식베이스 확장점.** `knowledge/*.yaml` 한 개 추가 = 코드 수정 0. 오픈소스 기여 유도점으로
  의도적으로 설계됐고 실제로 그렇게 동작한다(PostgreSQL 추가가 그 증거).
- **신뢰 경계가 코드에 새겨져 있다.** 평문 값은 백엔드 메모리에만 있고, 프론트 스토어는
  `preview`(앞뒤 4글자)만 보유한다(`types.ts` 의 `VaultItem.preview` 주석).
- **권한 방향으로 나눈 엔드포인트 정책.** 권한을 넓히는 쪽(디렉토리 등록·승인)은 잠금 해제 필수,
  좁히는 쪽(해제·거부)과 조회는 잠금 상태에서도 허용. `main.py` 에 근거가 주석으로 남아 있다.
- **결정 근거의 문서화.** `docs/memo/`, `docs/feature-ledger.html` 에 "왜 그렇게 했는지"와
  "무엇을 택하지 않았는지"가 남아 있다. 합류자가 가장 먼저 필요로 하는 자산이다.

---

## 2. 문제 영역

측정값 기준으로 심각한 순서.

| # | 문제 | 근거(측정) | 위험 |
|---|------|-----------|------|
| 1 | `keylensStore.ts` 단일 파일 비대 | **1,736줄**, 상태 **170개**, 액션 **104개** (프론트의 21%) | 높음 |
| 2 | `vault_session` 연결 관리 중복 | `conn = self._conn()` + try/finally **25회** | 중간 |
| 3 | `main.py` 예외 변환 중복 | `except VaultLocked` → 401 **12회**, 라우트 **35개**/633줄 | 중간 |
| 4 | 스토어 에러 처리 산재 | `vaultErrorText` **21곳**, 401 잠금 반영은 **5곳만** | 중간 |
| 5 | 죽은 코드와 유령 의존성 | `src/ocr/` **전 모듈 미참조**, 그 테스트 **15개**가 죽은 코드 검증 | 중간 |
| 6 | DataGrid 하나 때문에 MUI 전체 | `@mui` **24MB** + `@emotion` 2.4MB, 사용처 **1개 컴포넌트** | 낮음 |
| 7 | 매 연결마다 스키마 보장 | `connect()` **0.70ms** vs 순수 연결 0.13ms (**5배**) | 낮음 |

### 2.1 가장 큰 위험 - 스토어 단일 파일

`keylensStore.ts` 하나가 부팅·잠금·입력·분류·보관함·내보내기·SDK 승인·초기화를 전부 들고 있다.
이미 주석으로 **13개 섹션**이 나뉘어 있다는 게 역설적으로 이 파일이 여러 모듈이라는 증거다.

```
518  부팅/금고 로딩   873  설정       905  잠금/해제    947  입력
1049 직접 입력        1124 결과 카드   1251 보관함      1462 .env 내보내기
1510 금고 내보내기    1587 화면 설명   1621 완전 초기화
```

**실제로 비용을 치른 사례**: 오늘 잡은 "승인 후 허용 목록 미갱신" 버그(`1388052`)는
`approvePending` 이 `loadPending` 만 부르고 `allSdkDirs` 를 잊은 것이었다. 두 상태가 파일
1,700줄 안에 흩어져 있으면 "이 액션이 건드려야 할 상태"를 한눈에 볼 수 없다.

### 2.2 죽은 코드가 테스트를 갖고 있다

`src/ocr/ocr.ts`(tesseract.js 브라우저 OCR)와 `src/ocr/reconstruct.ts` 는 **어느 파일도
import 하지 않는다.** CORE-3 에서 백엔드 RapidOCR 로 옮긴 뒤 남은 잔재다.

> **정정(2026-09-04, 실제 제거 작업 중)**: 처음 이 절을 쓸 때 "JS 번들에서는 트리셰이킹되므로
> 영향이 작다"고 판단했는데 **틀렸다.** JS 는 트리셰이킹되지만 `package.json` 의
> `prebuild` 가 매 빌드마다 `vendor-tesseract.mjs` 를 돌려 WASM·언어데이터를
> `public/tesseract`(44MB)·`public/tessdata`(3MB)에 벤더링하고, `public/` 은 통째로 `dist/`
> 로 복사된다. 그리고 `desktop/setup.py` 가 `frontend/dist` 를 exe 에 동봉한다.
> 즉 **175MB 릴리스의 약 4분의 1이 아무도 호출하지 않는 OCR 자산**이었다.
> 번들 분석은 JS 뿐 아니라 정적 자산까지 봐야 한다 - 내가 그 절반만 보고 결론을 냈다.

다음이 남는다.

- `tesseract.js` 가 **런타임 의존성**으로 선언돼 있어 `npm ci --omit=dev` 설치·SBOM·공급망
  점검 대상에 계속 잡힌다. `docs/SBOM.md` 는 이미 "레거시"로 표시해 뒀다 - 알면서 남긴 상태다.
- `reconstruct.test.ts` 의 **테스트 15개**가 아무도 안 쓰는 코드를 지킨다. 프론트 테스트
  75개 중 20%다. 초록불이 실제 보호 범위를 부풀린다.
- `@radix-ui/react-select` 는 import 0곳 - 완전한 유령 의존성.

### 2.3 성능 - 정직하게 말하면 병목은 없다

측정: `vault_repo.connect()` 200회 139.3ms(평균 **0.70ms**), 순수 `sqlite3.connect()` 26.1ms
(평균 0.13ms). 스키마 보장이 **0.57ms/회**를 더한다. `list_entries()` 는 50개 항목에 1.79ms.

**로컬 단일 사용자 앱에서 이건 체감되지 않는다.** 병목이라고 부르면 과장이다. 다만 구조적으로는
낭비다 - `_conn()` 호출 지점이 25곳이고, 승인 대기 화면은 `PENDING_POLL_MS = 5000` 으로 5초마다
폴링한다. "매 연결마다 전체 스키마를 다시 실행"은 규모가 커질 때 먼저 무너지는 종류의 설계다.

> 이 비용은 오늘 내가 만들었다. 금고 생성 전 SDK 500 을 고치며 `connect()` 의 조건을 없앴다
> (`e74417c`). 옳은 수정이었지만 대가를 기록해 둔다.

---

## 3. 리팩토링 전략

**원칙**: 기능 불변. 각 항목은 독립적으로 되돌릴 수 있어야 하고, 기존 테스트가 그대로
통과해야 한다(테스트 수정이 필요하면 그건 동작이 바뀌었다는 신호다 - 4.1 은 예외이며 이유를 적었다).

| 순서 | 작업 | 위험 | 근거 |
|------|------|------|------|
| 1 | 죽은 코드·유령 의존성 제거 | **매우 낮음** | 참조 0곳이 이미 증명됨 |
| 2 | `main.py` 예외 변환을 핸들러로 | 낮음 | 12곳 → 1곳, 상태코드 테스트가 보증 |
| 3 | `vault_session` 연결 컨텍스트 매니저 | 낮음 | 25곳의 기계적 치환 |
| 4 | 스토어 슬라이스 분할 | 중간 | 13개 섹션이 이미 seam. 한 번에 하지 말 것 |
| 5 | 스키마 보장을 `user_version` 으로 | 낮음 | 자가 치유 유지가 조건 |
| 6 | MUI 제거(DataGrid 자체 구현) | 중간 | 이득 대비 비용을 먼저 재라 |

**4번은 한 번에 하지 마라.** 슬라이스 분할은 13개를 동시에 옮기면 리뷰가 불가능해진다.
섹션 하나씩, 커밋 하나씩. 옮길 때 액션이 건드리는 상태를 같은 파일에 모으는 게 목적이지
파일 수를 늘리는 게 목적이 아니다.

**6번은 지금 권하지 않는다.** MUI 는 설치 24MB지만 번들에 실제로 들어가는 건 DataGrid 관련
일부다. 직접 구현하면 정렬·가상 스크롤·접근성을 다시 만들어야 하고, 그건 기능 불변 리팩토링이
아니라 재작성이다. 남긴다면 **왜 남기는지**를 주석으로 적는 편이 낫다.

---

## 4. 개선된 코드

### 4.1 `main.py` - 예외 변환을 한 곳으로 (12곳 → 1곳)

**현재**: 라우트마다 같은 변환이 반복된다.

```python
@app.post("/vault/entries", response_model=VaultEntryMeta)
def vault_add(body: VaultEntryCreate) -> VaultEntryMeta:
    try:
        meta = VAULT.add_entry(...)
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 - 인증하세요") from None
    return VaultEntryMeta(**meta)
```

**개선**: FastAPI 예외 핸들러로 올린다. 도메인 예외를 그대로 던지고 변환은 한 곳에서 한다.

```python
# app/main.py - 앱 생성 직후 한 번만
@app.exception_handler(VaultLocked)
async def _handle_vault_locked(_: Request, __: VaultLocked) -> JSONResponse:
    """금고 잠김을 401 로 변환한다.

    라우트마다 try/except 를 두면 새 라우트에서 빠뜨렸을 때 500 이 샌다. 실제로 이번에
    /sdk/pending 이 가드를 빠뜨려 500 을 냈다(e74417c). 변환을 한 곳에 두면 빠뜨릴 자리가 없다.
    """
    return JSONResponse(status_code=401, content={"detail": "금고가 잠겨 있습니다 - 인증하세요"})


@app.exception_handler(VaultRateLimited)
async def _handle_rate_limited(_: Request, exc: VaultRateLimited) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)},
        headers={"Retry-After": str(int(exc.retry_after))},
    )
```

라우트는 이렇게 줄어든다.

```python
@app.post("/vault/entries", response_model=VaultEntryMeta)
def vault_add(body: VaultEntryCreate) -> VaultEntryMeta:
    return VaultEntryMeta(**VAULT.add_entry(...))
```

> **주의**: 라우트 함수를 직접 호출하는 기존 테스트(`main.vault_add(...)`)는 예외 핸들러를
> 거치지 않으므로 `HTTPException` 대신 `VaultLocked` 가 올라온다. 테스트를 함께 바꿔야 하고,
> 그건 "동작이 바뀌었다"가 아니라 "테스트가 HTTP 계층을 우회하고 있었다"는 뜻이다.
> 이 항목만은 테스트 수정이 정당하다 - 다만 그 판단을 커밋 메시지에 남길 것.

### 4.2 `vault_session.py` - 연결 컨텍스트 매니저 (25곳)

**현재**: 같은 6줄이 25번 반복된다.

```python
def list_entries(self) -> list[dict]:
    conn = self._conn()
    try:
        return vault_repo.list_entries(conn)
    finally:
        conn.close()
```

**개선**:

```python
from contextlib import contextmanager

@contextmanager
def _open(self):
    """연결을 열고 반드시 닫는다.

    25곳에서 반복되던 try/finally 를 한 곳으로 모은다. 닫기를 빠뜨리면 SQLite 파일 핸들이
    남아 Windows 에서 파일 잠금 문제로 이어지므로, 반복 대신 강제되는 형태가 낫다.
    """
    conn = self._conn()
    try:
        yield conn
    finally:
        conn.close()

def list_entries(self) -> list[dict]:
    with self._open() as conn:
        return vault_repo.list_entries(conn)
```

기계적 치환이라 위험이 낮고, 기존 테스트가 그대로 보증한다.

### 4.3 `vault_repo.connect()` - 스키마 보장을 버전 확인으로

**현재**: 연결마다 `executescript(_SCHEMA)` + `PRAGMA table_info` 2회 + `CREATE INDEX` 2회.

**개선**: SQLite 표준 패턴인 `user_version` 을 쓴다. 프로세스 캐시(경로를 집합에 기억)로
하지 않는 이유가 있다 - 파일이 밖에서 지워지면 캐시가 거짓이 되어 자가 치유가 깨진다.
`user_version` 은 파일 자체에 있으므로 새 파일이면 0 이라 자연히 다시 마이그레이션된다.

```python
_SCHEMA_VERSION = 1

def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # 파일에 새겨진 버전으로 판단한다. 프로세스 메모리에 캐시하면 파일이 밖에서 지워졌을 때
    # "이미 했다"고 착각해 스키마 없는 db 를 쓰게 된다 - 지금의 자가 치유 성질을 잃는다.
    if conn.execute("PRAGMA user_version").fetchone()[0] < _SCHEMA_VERSION:
        conn.executescript(_SCHEMA)
        _ensure_path_norm_column(conn, "sdk_project_dirs")
        _ensure_path_norm_column(conn, "sdk_pending_requests")
        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        conn.commit()
    return conn
```

`PRAGMA user_version` 읽기는 헤더에서 나오므로 사실상 공짜다.
**단, 이 변경은 반드시 "구버전 db 업그레이드" 테스트와 함께 가야 한다** - `user_version` 이
0 인 기존 금고가 정확히 한 번 마이그레이션되는지가 유일한 위험이다.

### 4.4 스토어 - 금고 액션 래퍼 (에러 처리 21곳)

**현재**: 액션마다 같은 catch 를 쓰는데, 401 잠금 반영은 **5곳에만** 있다. 나머지는 빠졌다.

```typescript
try {
  await sdkApi.approve(id)
  await get().loadPending()
} catch (e) {
  if (e instanceof VaultApiError && e.status === 401) set({ locked: true })
  get().showToast(vaultErrorText(e, '허용 실패'))
}
```

**개선**: 잠금 반영을 빠뜨릴 수 없는 형태로 만든다.

```typescript
/**
 * 금고 API 호출을 감싼다. 401 은 **항상** 잠금 상태에 반영한다.
 *
 * 지금은 액션마다 손으로 적고 있어서 21곳 중 5곳에만 들어가 있다. 빠진 곳에서 세션이
 * 만료되면 화면은 "열린 상태"인데 모든 요청이 실패하는, 사용자가 원인을 알 수 없는 상태가 된다.
 */
async function runVaultAction<T>(
  set: (p: Partial<KeylensState>) => void,
  get: () => KeylensState,
  fn: () => Promise<T>,
  fallbackMsg: string,
): Promise<T | undefined> {
  try {
    return await fn()
  } catch (e) {
    if (e instanceof VaultApiError && e.status === 401) set({ locked: true })
    get().showToast(vaultErrorText(e, fallbackMsg))
    return undefined
  }
}

// 사용
approvePending: async (id) => {
  const ok = await runVaultAction(set, get, async () => {
    await sdkApi.approve(id)
    await Promise.all([get().loadPending(), get().loadAllSdkDirs()])
    return true
  }, '허용 실패 - 잠시 후 다시 시도해 보세요')
  if (ok) get().showToast('요청을 허용했어요 - 이후 자동으로 값을 받아갑니다')
},
```

### 4.5 죽은 코드 제거 (가장 먼저 할 것)

```bash
git rm -r frontend/src/ocr/            # ocr.ts, reconstruct.ts, reconstruct.test.ts
npm uninstall tesseract.js @radix-ui/react-select
```

그리고 `docs/SBOM.md` 의 tesseract.js 4줄(본체 + 전이 의존성 3개)을 제거한다.

**실제 효과(2026-09-04 적용 후 측정)**:

| | 이전 | 이후 |
|---|---|---|
| `frontend/dist` | 50 MB | **3.5 MB** |
| 프론트 테스트 | 75개 | 60개 (죽은 코드를 지키던 15개 제거) |
| SBOM 항목 | - | **12건 제거**(tesseract.js + 전이 8건, radix-select, 자산 2건) |
| 프론트 런타임 라이선스 | Apache-2.0 포함 | MIT 115 · BSD-3 3 · ISC 2 · 0BSD 1 (Apache 0) |
| 빌드 단계 | `prebuild` 에서 WASM 벤더링 | 폰트 벤더링만 |

`dist` 는 `desktop/setup.py` 를 통해 exe 에 그대로 들어가므로, 이 감축은 릴리스 zip 크기로
직접 이어진다.

> `src/ocr/reconstruct.ts` 의 OCR 재구성 로직은 백엔드로 옮겨진 개념이다. 지우기 전에
> `backend/app/ocr.py` 에 대응 로직이 있는지 확인하고, 없다면 지우지 말고 **왜 남기는지**를
> 주석으로 적어라. 아이디어가 코드에만 남아 있으면 지우는 순간 사라진다.

---

## 5. 하지 말아야 할 것

합류자가 흔히 저지르는 실수를 미리 적어 둔다.

- **`lock()` 에서 인증 백오프를 지우지 마라.** 오늘 그 유혹이 있었다(`a11a8e2`).
  `/vault/lock` 은 인증이 없어서, 거기서 지우면 공격자가 추측 사이사이에 잠금을 걸어
  지수 백오프를 무력화할 수 있다.
- **`.env` 파싱을 백엔드 `/analyze` 로 통합하지 마라.** 중복처럼 보이지만 아니다.
  `/analyze` 는 **값 기준**으로 중복을 제거해서, 같은 값을 쓰는 `DATABASE_URL` 과 `DB_URL`
  중 하나를 조용히 잃는다. 프론트 파싱은 그걸 피하려는 의도적 분리다.
- **`connect()` 의 스키마 보장을 프로세스 캐시로 바꾸지 마라.** 4.3 참고 - 자가 치유가 깨진다.
- **예외·`HTTPException(detail=...)` 문자열에 em dash 를 쓰지 마라.** cp949 콘솔에서
  프로세스가 죽는다. `tests/test_console_safe_messages.py` 가 막지만, 이유를 알고 있어야 한다.

---

## 6. 요약

이 코드베이스는 **결정 근거가 잘 남아 있고 테스트가 소스보다 큰** 잘 관리된 저장소다.
구조적으로 급한 문제는 없다. 다만 프론트 스토어 하나가 21%를 차지하며 커지고 있고, 그 비대함이
오늘 실제 버그 하나의 원인이 됐다.

권하는 순서는 **죽은 코드 제거 → 예외 변환 통합 → 연결 컨텍스트 매니저 → 스토어 슬라이스 분할**이다.
앞의 셋은 하루 안에 끝나고 위험이 거의 없다. 마지막은 섹션 하나씩, 여러 커밋으로 나눠서 한다.

성능은 지금 손댈 이유가 없다. 측정해 보니 체감 가능한 병목이 없었고, "빠르게 만들자"는 근거
없는 변경은 이 저장소가 가진 가장 큰 자산 - **왜 그렇게 했는지가 남아 있다는 점** - 을 갉아먹는다.
