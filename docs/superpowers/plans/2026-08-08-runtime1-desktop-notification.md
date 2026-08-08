<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# RUNTIME-1 데스크톱 승인 알림 + 최소 승인 대기 화면 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `keylens-env` SDK가 미등록 디렉토리에서 값을 요청해 승인 대기열에 올라갈 때, 데스크톱 앱이 그 순간을 사용자에게 알리고(작업표시줄 깜빡임 + OS 토스트 + 화면 자동 전환), 사용자가 그 자리에서 허용/거부할 수 있는 최소 화면(`PendingScreen`)을 만든다. 설계는 `docs/superpowers/specs/2026-08-07-runtime1-desktop-notification-design.md`에서 확정됨.

**Architecture:** 세 계층. (1) 백엔드 `VaultService`에 `on_pending` 콜백 훅을 추가해 `sdk_env()`가 새 대기 요청을 대기열에 등록하는 순간 훅을 1회 호출한다(기본은 no-op — dev/테스트 영향 0). (2) 데스크톱 레이어 `desktop/notify.py`가 그 훅의 실제 구현(작업표시줄 깜빡임·OS 토스트·`evaluate_js`로 SPA 전환)을 담당하고, 전부 try/except로 감싸 실패해도 SDK 요청 흐름을 깨지 않는다. (3) 프론트에 새 `pending` 뷰(`PendingScreen`) + Zustand 스토어 액션(`goPending`/`loadPending`/`approvePending`/`denyPending`) + `window.__keylensGoPending` 전역 진입점을 추가해, 데스크톱이 `evaluate_js`로 그 진입점을 호출하면 이미 존재하는 SPA가 즉시 승인 대기 화면으로 전환된다. `/sdk/pending`·`/sdk/pending/{id}/approve`·`/sdk/pending/{id}/deny` API는 이미 구현되어 있다(`backend/app/main.py`) — 이 플랜은 그 위에 훅·알림·화면만 얹는다.

**Tech Stack:** Python 3.11+(FastAPI·pywebview) / React 19 + TypeScript + Zustand(프론트) / `plyer==2.1.0`(MIT, 신규 — license-auditor 승인 완료: 전이 의존성 없음, Windows 경로는 순수 stdlib `ctypes`만 사용) / `ctypes`(표준 라이브러리, Windows `FlashWindowEx`).

## Global Constraints

- 새 런타임 의존성은 `plyer==2.1.0`(MIT) 하나만 — 그 외 전부 기존 모듈 재사용. 카피레프트(GPL/AGPL/LGPL/MPL) 의존성 추가 금지.
- 모든 새 파일 맨 위에 SPDX 헤더 2줄: 파이썬은 `# SPDX-FileCopyrightText: 2026 [Your Name]` / `# SPDX-License-Identifier: MIT`, TS/TSX는 `// SPDX-FileCopyrightText: 2026 [Your Name]` / `// SPDX-License-Identifier: MIT`.
- 알림 로직(`desktop/notify.py`)은 전부 best-effort — 어느 하나가 실패해도 예외를 밖으로 던지면 안 된다(SDK 요청 자체를 깨면 안 됨).
- Windows 우선(작업표시줄 깜빡임은 `sys.platform == 'win32'` 가드). macOS/Linux 알림은 이 플랜 범위 밖.
- 토스트 클릭 콜백에 의존하지 않는다 — 새 요청 발생 즉시(클릭 여부 무관) SPA를 승인 대기 화면으로 전환해 둔다(설계 스펙의 핵심 판단).
- 값(시크릿) 자체는 이 플랜에서 전혀 다루지 않는다 — 프로젝트명·경로 문자열만 오간다.
- 에러 메시지는 항상 사람이 읽을 수 있는 한국어 문자열로(기존 관례).
- 프론트 "디렉토리 등록" 설정 화면은 범위 밖(별도 서브플랜) — 이번엔 승인 대기 목록만.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`.

---

### Task 1: 백엔드 — `sdk_repo.is_pending` + `VaultService.on_pending` 훅

**Files:**
- Modify: `backend/app/sdk_repo.py` (76번째 줄 `is_path_approved` 함수 바로 뒤, `add_pending_request` 앞에 `is_pending` 추가)
- Modify: `backend/app/vault_session.py` (`__init__` 시그니처, 새 메서드 `set_pending_hook`, `sdk_env` 본문)
- Test: `backend/tests/test_sdk_repo.py` (파일 끝에 추가), `backend/tests/test_sdk_session.py` (파일 끝에 추가)

**Interfaces:**
- Consumes: `sdk_repo._normalize_path`(기존, 비공개지만 같은 모듈), `sdk_repo.add_pending_request`/`is_path_approved`(기존)
- Produces (Task 5/6이 그대로 씀):
  - `sdk_repo.is_pending(conn: sqlite3.Connection, project: str, path: str) -> bool`
  - `VaultService.__init__(..., on_pending: Callable[[str, str], None] | None = None)`
  - `VaultService.set_pending_hook(self, fn: Callable[[str, str], None] | None) -> None`

- [ ] **Step 1: 실패하는 테스트 작성 — `backend/tests/test_sdk_repo.py` 끝에 추가**

```python
def test_is_pending_false_initially(conn):
    assert sdk_repo.is_pending(conn, "블로그", "/repo/blog") is False


def test_is_pending_true_after_add(conn):
    sdk_repo.add_pending_request(conn, "블로그", "/repo/blog")
    assert sdk_repo.is_pending(conn, "블로그", "/repo/blog") is True


def test_is_pending_false_after_approve(conn):
    pid = sdk_repo.add_pending_request(conn, "블로그", "/repo/blog")
    sdk_repo.approve_pending(conn, pid)
    assert sdk_repo.is_pending(conn, "블로그", "/repo/blog") is False
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_repo.py -v -k is_pending`
Expected: `AttributeError: module 'app.sdk_repo' has no attribute 'is_pending'`

- [ ] **Step 3: `backend/app/sdk_repo.py`에 `is_pending` 추가**

`is_path_approved` 함수(76번째 줄) 바로 뒤, `add_pending_request` 함수 앞에 삽입:

```python
def is_pending(conn: sqlite3.Connection, project: str, path: str) -> bool:
    """path가 project에 대해 이미 대기열에 올라와 있는지."""
    norm = _normalize_path(path)
    row = conn.execute(
        "SELECT 1 FROM sdk_pending_requests WHERE project = ? AND path_norm = ?",
        (project, norm),
    ).fetchone()
    return row is not None
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_repo.py -v`
Expected: 전부 통과(기존 15개 + 신규 3개 = 18개)

- [ ] **Step 5: 실패하는 테스트 작성 — `backend/tests/test_sdk_session.py` 끝에 추가**

```python
def test_set_pending_hook_called_once_for_new_request(vault):
    calls = []
    vault.set_pending_hook(lambda project, path: calls.append((project, path)))
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    assert calls == [("블로그", "/repo/blog")]


def test_set_pending_hook_not_called_again_for_duplicate_request(vault):
    calls = []
    vault.set_pending_hook(lambda project, path: calls.append((project, path)))
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    assert len(calls) == 1


def test_pending_hook_defaults_to_noop(tmp_path):
    svc = VaultService(str(tmp_path / "vault.db"), auto_lock_seconds=60)
    svc.init(MASTER)
    with pytest.raises(SdkApprovalPending):
        svc.sdk_env("블로그", "/repo/blog")  # 훅 미등록이어도 예외 없이 정상 동작(no-op)


def test_pending_hook_not_called_when_path_already_approved(vault):
    calls = []
    vault.set_pending_hook(lambda project, path: calls.append((project, path)))
    vault.add_project_dir("블로그", "/repo/blog")
    env = vault.sdk_env("블로그", "/repo/blog")
    assert env == {}
    assert calls == []


def test_set_pending_hook_can_be_cleared(vault):
    calls = []
    vault.set_pending_hook(lambda project, path: calls.append((project, path)))
    vault.set_pending_hook(None)
    with pytest.raises(SdkApprovalPending):
        vault.sdk_env("블로그", "/repo/blog")
    assert calls == []
```

- [ ] **Step 6: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_session.py -v -k pending_hook`
Expected: `AttributeError: 'VaultService' object has no attribute 'set_pending_hook'`

- [ ] **Step 7: `backend/app/vault_session.py` 수정**

`__init__` 시그니처(40번째 줄)를 바꾼다:

```python
    def __init__(
        self,
        db_path: str,
        auto_lock_seconds: int = AUTO_LOCK_SECONDS,
        fail_free: int = FAIL_FREE,
        max_delay: int = MAX_DELAY,
        clock: Callable[[], float] = time.time,
        on_pending: Callable[[str, str], None] | None = None,
    ) -> None:
        self.db_path = db_path
        self.auto_lock_seconds = auto_lock_seconds
        self.fail_free = fail_free
        self.max_delay = max_delay
        self._clock = clock
        self._on_pending = on_pending
        self._key: bytes | None = None
        self._last_activity = 0.0
        self._fail_count = 0
        self._locked_until = 0.0
```

`sdk_env` 메서드(292번째 줄 근방, `# ── RUNTIME-1: SDK 접근 관리 ──` 섹션의 첫 메서드) 본문을 바꾼다:

```python
    def sdk_env(self, project: str, path: str) -> dict[str, str]:
        """keylens-env SDK 진입점. path가 project에 대해 승인되지 않았으면 대기열에 등록하고
        SdkApprovalPending을 던진다. 승인됐으면 값을 복호화해 반환하고, 반환한 각 키를
        감사 이력에 'sdk_fetch'로 남긴다. 잠금 상태면 VaultLocked(값은 절대 안 나감).

        SDK 조회는 자동 잠금 타이머를 갱신하지 않는다 — 자리를 비운 사용자를 보호하기 위함.
        새로 대기열에 등록되는 요청에 한해 on_pending 훅을 1회 호출한다(이미 대기 중인
        경로의 재요청은 다시 호출하지 않는다 — idempotent).
        """
        key = self._require_key(refresh=False)
        conn = self._conn()
        try:
            if not sdk_repo.is_path_approved(conn, project, path):
                already_pending = sdk_repo.is_pending(conn, project, path)
                sdk_repo.add_pending_request(conn, project, path)
                if not already_pending and self._on_pending is not None:
                    self._on_pending(project, path)
                raise SdkApprovalPending(
                    f"'{path}'가 '{project}' 프로젝트 키를 요청했어요 — KeyLens에서 허용해 주세요"
                )
            env = sdk_repo.entries_for_env(conn, key, project)
            ids = sdk_repo.entry_ids_for_names(conn, project, list(env.keys()))
            for entry_id in ids.values():
                vault_repo.log_access(conn, entry_id, "sdk_fetch")
            return env
        finally:
            conn.close()
```

`change_password` 메서드 뒤, `# ── RUNTIME-1: SDK 접근 관리 ──` 섹션 안(어디든, 예: `sdk_env` 바로 뒤)에 새 메서드를 추가:

```python
    def set_pending_hook(self, fn: Callable[[str, str], None] | None) -> None:
        """승인 대기 발생 시 호출할 콜백을 등록(데스크톱 알림용, RUNTIME-1). None이면 해제(no-op)."""
        self._on_pending = fn
```

- [ ] **Step 8: 테스트 실행 → 전체 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_sdk_session.py -v`
Expected: 전부 통과(기존 11개 + 신규 5개 = 16개)

- [ ] **Step 9: 회귀 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: 실패 0.

- [ ] **Step 10: 커밋**

```bash
git add backend/app/sdk_repo.py backend/app/vault_session.py backend/tests/test_sdk_repo.py backend/tests/test_sdk_session.py
git commit -m "feat(backend): RUNTIME-1 승인 대기 훅(on_pending) — 새 요청에 한해 1회 발화

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: 프론트 — 타입 + API 클라이언트 (`sdkApi`)

**Files:**
- Modify: `frontend/src/api/types.ts` (파일 끝에 `SdkPendingRequest` 추가)
- Modify: `frontend/src/api/client.ts` (파일 끝에 `sdkApi` 추가)
- Modify: `frontend/src/types.ts` (`View`에 `'pending'` 추가, `PendingRequest` 인터페이스 추가)

**Interfaces:**
- Consumes: `vreq<T>`(기존, `frontend/src/api/client.ts`), `API_BASE`(기존, 같은 파일)
- Produces (Task 3이 그대로 씀):
  - `SdkPendingRequest { id: number; project: string; path: string; requested_at: string }` (API 계약, snake_case)
  - `sdkApi.pending(): Promise<SdkPendingRequest[]>`
  - `sdkApi.approve(id: number): Promise<{ approved: boolean }>`
  - `sdkApi.deny(id: number): Promise<{ denied: boolean }>`
  - `View = 'input' | 'vault' | 'pending'`
  - `PendingRequest { id: number; project: string; path: string; requestedAt: string }` (프론트 내부, camelCase)

- [ ] **Step 1: `frontend/src/api/types.ts` 파일 끝에 추가**

```typescript
/** 승인 대기 요청 한 건(RUNTIME-1) — 값 없이 프로젝트·경로 문자열만. */
export interface SdkPendingRequest {
  id: number
  project: string
  path: string
  requested_at: string
}
```

- [ ] **Step 2: `frontend/src/api/client.ts` 파일 끝에 추가**

파일 상단 import 블록의 타입 목록에 `SdkPendingRequest`를 추가(알파벳 순서 유지):

```typescript
import type {
  AnalyzeApiRequest,
  AnalyzeApiResponse,
  KnowledgeResponse,
  SdkPendingRequest,
  VaultEntryCreate,
  VaultEntryMeta,
  VaultEntryUpdate,
  VaultHistoryEntry,
  VaultBundle,
  VaultImportResult,
  VaultStatus,
  VaultVerifyResult,
} from './types'
```

파일 맨 끝(`vaultApi` 객체 뒤)에 추가:

```typescript
// ── RUNTIME-1: SDK 접근 관리 — 승인 대기 목록만(디렉토리 등록 설정화면은 범위 밖) ──

export const sdkApi = {
  pending: () => vreq<SdkPendingRequest[]>('/sdk/pending'),
  approve: (id: number) => vreq<{ approved: boolean }>(`/sdk/pending/${id}/approve`, { method: 'POST' }),
  deny: (id: number) => vreq<{ denied: boolean }>(`/sdk/pending/${id}/deny`, { method: 'POST' }),
}
```

- [ ] **Step 3: `frontend/src/types.ts` 수정**

`View` 타입(14번째 줄)을 바꾼다:

```typescript
/** 앱 셸 내부 뷰. */
export type View = 'input' | 'vault' | 'pending'
```

파일 끝에 추가:

```typescript
/** 승인 대기 요청 한 건(RUNTIME-1, 프론트 내부 표현). */
export interface PendingRequest {
  id: number
  project: string
  path: string
  requestedAt: string
}
```

- [ ] **Step 4: 타입체크로 확인(테스트 없음 — 순수 타입/클라이언트 추가라 기존 프로젝트 관례상 API 클라이언트에 단위테스트 없음)**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 0(아직 `sdkApi`·`PendingRequest`를 쓰는 곳이 없어도, 새로 추가한 타입 자체는 컴파일 통과해야 함)

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/types.ts
git commit -m "feat(frontend): RUNTIME-1 sdkApi 클라이언트 + PendingRequest 타입

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: 프론트 — 스토어 (`pendingRequests` 상태 + 액션)

**Files:**
- Modify: `frontend/src/store/keylensStore.ts`

**Interfaces:**
- Consumes: `sdkApi`(Task 2), `PendingRequest`(Task 2), `vaultApi`(기존), `VaultApiError`(기존), `vaultErrorText`(기존, 같은 파일 35번째 줄)
- Produces (Task 4가 그대로 씀):
  - `state.pendingRequests: PendingRequest[]`
  - `goPending(): void` — `view`를 `'pending'`으로 바꾸고 목록을 새로 불러온다
  - `loadPending(): Promise<void>`
  - `approvePending(id: number): Promise<void>`
  - `denyPending(id: number): Promise<void>`

- [ ] **Step 1: import 추가**

`frontend/src/store/keylensStore.ts` 9번째 줄의 import를 바꾼다:

```typescript
import { analyzeApi, ApiError, fetchKnowledge, sdkApi, vaultApi, VaultApiError } from '@/api/client'
```

23번째 줄 근방의 타입 import 블록에 `PendingRequest`를 추가(알파벳 순서 유지):

```typescript
import type {
  AnalysisResult,
  DeleteTarget,
  DupTarget,
  InputMode,
  ManualRow,
  PendingRequest,
  Screen,
  UnknownItem,
  VaultItem,
  View,
} from '@/types'
```

- [ ] **Step 2: 인터페이스(`KeylensState`)에 상태·액션 시그니처 추가**

`knowledgeReady: boolean` 줄(126번째 줄) 바로 뒤에 상태 필드 추가:

```typescript
  /** RUNTIME-1 승인 대기 목록(값 없음 — 프로젝트·경로 문자열만). */
  pendingRequests: PendingRequest[]
```

`goVault: () => void` 줄(144번째 줄) 바로 뒤에 액션 시그니처 추가:

```typescript
  /** 승인 대기 화면으로 전환하고 목록을 새로 불러온다(데스크톱 알림이 evaluate_js로 호출하는 경로). */
  goPending: () => void
  /** 승인 대기 목록을 백엔드에서 다시 불러온다(값 없음 — 잠금 상태에서도 동작). */
  loadPending: () => Promise<void>
  /** 승인 대기 요청을 허용 — 이후 해당 디렉토리는 자동 통과. */
  approvePending: (id: number) => Promise<void>
  /** 승인 대기 요청을 거부. */
  denyPending: (id: number) => Promise<void>
```

- [ ] **Step 3: 초기 상태 값 추가**

`knowledgeReady: false,` 줄(286번째 줄) 바로 뒤에 추가:

```typescript
    pendingRequests: [],
```

- [ ] **Step 4: `boot()`에 최초 로딩 연결**

`boot` 액션(318번째 줄 근방) 안, `try { ... }` 블록 마지막(`if/else if/else` 분기 뒤, `catch` 앞)에 한 줄 추가:

```typescript
    boot: async () => {
      await get().loadKnowledge()
      try {
        const st = await vaultApi.status()
        if (!st.initialized) {
          set({ screen: 'setup' })
        } else if (st.unlocked) {
          set({ screen: 'app', locked: false })
          get().loadVault()
        } else {
          set({ screen: 'lock', locked: true })
        }
        get().loadPending()
      } catch (e) {
        console.error('[KeyLens] 부팅 시 금고 상태 조회 실패:', e)
        set({ screen: 'setup' })
        get().showToast('금고 기능을 쓰려면 KeyLens 서버가 켜져 있어야 해요 — 잠시 후 다시 시도해 보세요')
      }
    },
```

- [ ] **Step 5: 액션 구현 — `goInput: () => { ... }` 뒤(302~307번째 줄 근방)에 추가**

```typescript
    goPending: () => {
      set({ view: 'pending' })
      get().loadPending()
    },
```

- [ ] **Step 6: 액션 구현 — `loadHistory` 뒤(365번째 줄 근방, `// ── 설정(최초 실행) ──` 주석 앞)에 추가**

```typescript
    loadPending: async () => {
      try {
        const rows = await sdkApi.pending()
        set({
          pendingRequests: rows.map((r) => ({
            id: r.id,
            project: r.project,
            path: r.path,
            requestedAt: r.requested_at,
          })),
        })
      } catch {
        /* 목록 로딩 실패는 조용히 무시(뱃지·화면이 이전 상태 유지) */
      }
    },
    approvePending: async (id) => {
      try {
        await sdkApi.approve(id)
        await get().loadPending()
        get().showToast('요청을 허용했어요 — 이후 자동으로 값을 받아갑니다')
      } catch (e) {
        get().showToast(vaultErrorText(e, '허용 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },
    denyPending: async (id) => {
      try {
        await sdkApi.deny(id)
        await get().loadPending()
        get().showToast('요청을 거부했어요')
      } catch (e) {
        get().showToast(vaultErrorText(e, '거부 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },
```

- [ ] **Step 7: `resetProto()`에 리셋 추가**

`resetProto` 액션(1004번째 줄 근방) 안 `set({ ... })` 객체에 한 줄 추가:

```typescript
        syncOpen: false,
        pendingRequests: [],
```

- [ ] **Step 8: 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 0

- [ ] **Step 9: 커밋**

```bash
git add frontend/src/store/keylensStore.ts
git commit -m "feat(frontend): RUNTIME-1 스토어 — 승인 대기 목록 로딩/허용/거부 액션

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 4: 프론트 — `PendingScreen` + Sidebar 배지 + App.tsx 라우팅/전역 진입점

**Files:**
- Create: `frontend/src/components/screens/PendingScreen.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useKeylens`(기존), `state.pendingRequests`/`loadPending`/`approvePending`/`denyPending`/`goPending`(Task 3)
- Produces: `window.__keylensGoPending?: () => void`(전역, Task 5/6의 `desktop/notify.py`가 `evaluate_js`로 호출)

- [ ] **Step 1: `frontend/src/components/screens/PendingScreen.tsx` 생성**

```typescript
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect } from 'react'
import { useKeylens } from '@/store/keylensStore'

/** RUNTIME-1 — SDK 승인 대기 화면. 미등록 디렉토리의 keylens-env 요청을 확인해 허용/거부한다. */
export function PendingScreen() {
  const pendingRequests = useKeylens((s) => s.pendingRequests)
  const loadPending = useKeylens((s) => s.loadPending)
  const approvePending = useKeylens((s) => s.approvePending)
  const denyPending = useKeylens((s) => s.denyPending)

  // mount 시에도 직접 조회 — 수동 진입·다건 대기 케이스 커버(데스크톱 알림 없이도 확인 가능).
  useEffect(() => {
    loadPending()
  }, [loadPending])

  return (
    <div className="mx-auto max-w-[640px] px-8 pb-[90px] pt-[44px] [animation:klFadeUp_.35s_ease]">
      <div className="mb-[18px]">
        <h1 className="m-0 text-[20px] font-bold tracking-[-.015em]">승인 대기</h1>
        <div className="mt-1 text-[12.5px] text-faint-2">
          keylens-env SDK가 미등록 디렉토리에서 프로젝트 키를 요청했어요 — 허용해야 값을 내려줍니다.
        </div>
      </div>

      {pendingRequests.length === 0 ? (
        <div className="rounded-xl border border-border bg-panel px-5 py-8 text-center text-[13px] text-muted">
          대기 중인 요청이 없어요.
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {pendingRequests.map((r) => (
            <div
              key={r.id}
              className="flex items-center gap-3 rounded-xl border border-border bg-panel px-4 py-[14px]"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13.5px] font-semibold text-fg-soft">{r.project}</div>
                <div className="mt-[3px] truncate font-mono text-[11.5px] text-muted">{r.path}</div>
                <div className="mt-[3px] text-[10.5px] text-dim-3">{r.requestedAt}</div>
              </div>
              <button
                type="button"
                onClick={() => denyPending(r.id)}
                className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
              >
                거부
              </button>
              <button
                type="button"
                onClick={() => approvePending(r.id)}
                className="cursor-pointer rounded-lg border-none bg-mint px-3 py-[9px] text-[12.5px] font-bold text-on-mint hover:brightness-[1.07]"
              >
                허용
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: `frontend/src/components/Sidebar.tsx` 수정**

상단 훅 선언부(16~23번째 줄)에 추가:

```typescript
  const pendingCount = useKeylens((s) => s.pendingRequests.length)
  const goPending = useKeylens((s) => s.goPending)
```

`<nav>` 안(51~57번째 줄, `보관함` 버튼 뒤)에 새 버튼 추가:

```typescript
        <button type="button" onClick={goPending} className={navBtn(view === 'pending')}>
          <span className="block size-[15px] flex-none rounded-full border-[1.5px] border-current opacity-70" />
          <span className="flex-1">승인 대기</span>
          {pendingCount > 0 && (
            <span className="rounded-[10px] bg-[#E3B341] px-[7px] py-px text-[11px] font-semibold text-[#07231A]">
              {pendingCount}
            </span>
          )}
        </button>
```

- [ ] **Step 3: `frontend/src/App.tsx` 수정**

import 블록(6~9번째 줄)에 추가:

```typescript
import { PendingScreen } from '@/components/screens/PendingScreen'
```

`import { useEffect } from 'react'` 바로 뒤(3번째 줄 다음)에 전역 타입 선언 추가:

```typescript
declare global {
  interface Window {
    /** 데스크톱 알림(desktop/notify.py)이 evaluate_js로 호출하는 진입점 — 즉시 승인 대기 화면 전환. */
    __keylensGoPending?: () => void
  }
}
```

`export default function App() {` 안, 기존 `useEffect(() => { useKeylens.getState().boot() }, [])` 뒤에 새 `useEffect` 추가:

```typescript
  // 데스크톱 알림이 evaluate_js로 호출할 진입점 등록(RUNTIME-1).
  useEffect(() => {
    window.__keylensGoPending = () => useKeylens.getState().goPending()
    return () => {
      delete window.__keylensGoPending
    }
  }, [])
```

`<main>` 안의 뷰 분기(64번째 줄)를 바꾼다:

```typescript
          <main className="h-screen min-w-0 flex-1 overflow-y-auto">
            {view === 'input' && <InputScreen />}
            {view === 'vault' && <VaultScreen />}
            {view === 'pending' && <PendingScreen />}
          </main>
```

- [ ] **Step 4: 타입체크 + 린트 + 빌드**

Run: `cd frontend && npx tsc --noEmit && npm run lint && npm run build`
Expected: 에러 0

- [ ] **Step 5: 수동 브라우저 확인**

Run: `node scripts/dev.mjs` (루트에서) → `http://localhost:5173` 접속 → 로그인 → 사이드바 "승인 대기" 클릭 → 빈 상태("대기 중인 요청이 없어요") 확인. (실제 요청 생성은 Task 6까지 끝난 뒤 SDK 없이도 `curl -X POST http://localhost:8003/sdk/env -H "Content-Type: application/json" -d "{\"project\":\"테스트\",\"path\":\"/tmp/test\"}"` 로 시뮬레이션 가능 — 403 응답 후 사이드바 뱃지 "1" 확인, 화면에서 허용/거부 후 목록에서 사라지는지 확인.)

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/components/screens/PendingScreen.tsx frontend/src/components/Sidebar.tsx frontend/src/App.tsx
git commit -m "feat(frontend): RUNTIME-1 PendingScreen — 승인 대기 목록·허용/거부 + 사이드바 배지

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 5: 데스크톱 — `notify.py` (알림 로직) + 단위테스트

**Files:**
- Create: `desktop/notify.py`
- Create: `desktop/test_notify.py`
- Modify: `desktop/requirements.txt` (`plyer==2.1.0  # MIT` 추가)
- Modify: `desktop/setup.py` (`build_exe_options["packages"]`에 `"plyer"` 추가)

**Interfaces:**
- Consumes: 없음(순수 신규 모듈, pywebview 창 객체는 `evaluate_js(script: str) -> object` 메서드만 있으면 됨 — 덕 타이핑)
- Produces (Task 6이 그대로 씀):
  - `notify.build_notifier(window, title: str = "KeyLens") -> Callable[[str, str], None]` — `VaultService.set_pending_hook()`에 그대로 넘길 콜백

- [ ] **Step 1: `desktop/requirements.txt`에 의존성 추가**

파일 끝에 한 줄 추가:

```
plyer==2.1.0          # MIT; OS 네이티브 토스트(RUNTIME-1). 전이 의존성 없음(license-auditor 확인,
                       # Windows 경로는 plyer/platforms/win/libs/balloontip.py가 순수 stdlib ctypes만 사용)
```

- [ ] **Step 2: 의존성 설치(로컬 개발용 venv)**

Run: `cd backend && .venv/Scripts/pip.exe install -r ../desktop/requirements.txt`
Expected: `plyer` 설치 완료(다른 항목은 이미 설치돼 있어 스킵)

- [ ] **Step 3: 실패하는 테스트 작성 — `desktop/test_notify.py`**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 desktop/notify.py 유닛테스트 — 플랫폼 가드·예외 흡수만 검증.
OS 토스트·작업표시줄 깜빡임 자체는 수동 검증 대상(README 참고).
"""
import builtins
import sys

import notify


class FakeWindow:
    def __init__(self, raise_on_evaluate=False):
        self.calls = []
        self._raise = raise_on_evaluate

    def evaluate_js(self, script):
        self.calls.append(script)
        if self._raise:
            raise RuntimeError("boom")


def test_flash_taskbar_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    notify._flash_taskbar()  # 예외 없이 조용히 반환


def test_flash_taskbar_absorbs_exception(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    # 이 테스트 호스트가 실제 Windows가 아니면 ctypes.windll 자체가 없어 AttributeError가
    # 나지만, try/except로 흡수되어 예외가 밖으로 새면 안 된다(실제 Windows에서는 창을
    # 못 찾아 hwnd=0 → 조용히 반환하는 경로를 탄다 — 두 경우 모두 예외 없이 끝나야 함).
    notify._flash_taskbar()


def test_show_toast_absorbs_exception_when_plyer_missing(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "plyer":
            raise ImportError("plyer not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    notify._show_toast("블로그", "/repo/blog")  # 예외 없이 조용히 반환


def test_goto_pending_calls_evaluate_js():
    window = FakeWindow()
    notify._goto_pending(window)
    assert window.calls == ["window.__keylensGoPending && window.__keylensGoPending()"]


def test_goto_pending_absorbs_exception():
    window = FakeWindow(raise_on_evaluate=True)
    notify._goto_pending(window)  # RuntimeError 흡수, 밖으로 안 나옴


def test_build_notifier_calls_all_three_best_effort(monkeypatch):
    calls = []
    monkeypatch.setattr(notify, "_flash_taskbar", lambda *a, **k: calls.append("flash"))
    monkeypatch.setattr(
        notify, "_show_toast", lambda project, path: calls.append(("toast", project, path))
    )
    monkeypatch.setattr(notify, "_goto_pending", lambda w: calls.append(("goto", w)))

    window = FakeWindow()
    fn = notify.build_notifier(window)
    fn("블로그", "/repo/blog")

    assert calls == ["flash", ("toast", "블로그", "/repo/blog"), ("goto", window)]
```

- [ ] **Step 4: 테스트 실행 → 실패 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../desktop/test_notify.py -v`
Expected: `ModuleNotFoundError: No module named 'notify'`

- [ ] **Step 5: `desktop/notify.py` 생성**

```python
# SPDX-FileCopyrightText: 2026 [Your Name]
# SPDX-License-Identifier: MIT
"""RUNTIME-1 데스크톱 승인 알림 — 작업표시줄 깜빡임 + OS 토스트 + SPA 화면 전환.

전부 best-effort: 어느 하나가 실패해도 SDK 요청 흐름에 영향을 주지 않는다(그래서
build_notifier()의 결과를 VaultService.set_pending_hook()에 그대로 연결해도 안전하다).
사용자는 최소한 PendingScreen의 화면 안 배너로 뒤늦게라도 확인할 수 있다.
"""
from __future__ import annotations

import sys
from typing import Callable, Protocol


class _Window(Protocol):
    """pywebview 창 객체 중 이 모듈이 실제로 쓰는 부분만의 최소 인터페이스."""

    def evaluate_js(self, script: str) -> object: ...


def _flash_taskbar(title: str = "KeyLens") -> None:
    """작업표시줄 아이콘 깜빡임(Windows만, FlashWindowEx). 창을 제목으로 찾는다 —
    pywebview 내부 GUI 백엔드 구현에 의존하지 않기 위함. 실패하면 조용히 무시."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        if not hwnd:
            return

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        flashw_tray = 0x00000002
        flashw_timernofg = 0x0000000C
        info = FLASHWINFO(
            cbSize=ctypes.sizeof(FLASHWINFO),
            hwnd=hwnd,
            dwFlags=flashw_tray | flashw_timernofg,
            uCount=5,
            dwTimeout=0,
        )
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))
    except Exception:
        pass


def _show_toast(project: str, path: str) -> None:
    """OS 토스트(정보 제공용, 클릭 동작 없음). 실패하면 조용히 무시."""
    try:
        from plyer import notification

        notification.notify(
            title="KeyLens — 승인 대기",
            message=f"'{path}'가 '{project}' 프로젝트 키를 요청했어요",
            app_name="KeyLens",
            timeout=6,
        )
    except Exception:
        pass


def _goto_pending(window: _Window) -> None:
    """이미 떠 있는 SPA를 승인 대기 화면으로 즉시 전환. 실패하면 조용히 무시."""
    try:
        window.evaluate_js("window.__keylensGoPending && window.__keylensGoPending()")
    except Exception:
        pass


def build_notifier(window: _Window, title: str = "KeyLens") -> Callable[[str, str], None]:
    """VaultService.set_pending_hook()에 넘길 콜백을 만든다.

    반환한 함수는 무엇이 실패해도 절대 예외를 던지지 않는다 — 호출부인
    VaultService.sdk_env가 이 훅의 실패로 SDK 요청 자체를 깨뜨리면 안 되기 때문.
    """

    def notify(project: str, path: str) -> None:
        _flash_taskbar(title)
        _show_toast(project, path)
        _goto_pending(window)

    return notify
```

- [ ] **Step 6: 테스트 실행 → 전체 통과 확인**

Run: `cd backend && .venv/Scripts/python.exe -m pytest ../desktop/test_notify.py -v`
Expected: `7 passed`

- [ ] **Step 7: `desktop/setup.py` 수정**

`build_exe_options["packages"]` 리스트(34~36번째 줄)에 `"plyer"` 추가:

```python
build_exe_options = {
    "packages": [
        "app", "uvicorn", "fastapi", "starlette", "pydantic", "pydantic_core",
        "cryptography", "yaml", "webview", "anyio", "click", "h11", "plyer",
    ],
    "include_files": include_files,
    "excludes": ["tkinter", "unittest", "pytest", "test"],
}
```

- [ ] **Step 8: 커밋**

```bash
git add desktop/notify.py desktop/test_notify.py desktop/requirements.txt desktop/setup.py
git commit -m "feat(desktop): RUNTIME-1 notify.py — 작업표시줄 깜빡임 + OS 토스트 + SPA 전환(best-effort)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 6: 데스크톱 — `app.py`에 알림 훅 연결

**Files:**
- Modify: `desktop/app.py`

**Interfaces:**
- Consumes: `notify.build_notifier`(Task 5), `app.main.VAULT`(기존, `backend/app/main.py:68`), `VaultService.set_pending_hook`(Task 1)
- Produces: 없음(런처 진입점 — 이 태스크가 마지막 배선)

- [ ] **Step 1: `desktop/app.py`의 임포트 줄 수정**

46번째 줄을 바꾼다:

```python
from app.main import app, VAULT  # noqa: E402 — 경로·환경 설정 후 임포트
```

- [ ] **Step 2: `main()` 함수 수정**

84~95번째 줄의 `main()` 함수를 바꾼다:

```python
def main() -> None:
    import webview  # 지연 임포트 — 서버 검증(mount/serve)은 pywebview 없이도 돈다.

    import notify  # 지연 임포트 — 같은 이유(GUI 의존 없이 mount_spa/serve만 쓰는 경로 보호)

    mount_spa()
    threading.Thread(target=serve, daemon=True).start()
    if not _wait_ready():
        raise SystemExit("백엔드가 제때 기동하지 못했습니다.")
    # localhost 로 로드 → 페이지 오리진과 상대경로 API 요청이 같은 오리진(same-origin).
    window = webview.create_window(
        "KeyLens", f"http://localhost:{PORT}", width=1120, height=780, min_size=(900, 620)
    )
    VAULT.set_pending_hook(notify.build_notifier(window))
    webview.start()
```

- [ ] **Step 3: 소스 모드 수동 기동 확인**

Run(루트에서): `cd frontend && npm ci && npm run build && cd .. && python desktop/app.py`
Expected: 네이티브 창이 뜨고 마스터 비밀번호 화면(또는 잠금 화면)이 정상 표시. 콘솔에 임포트·타입 에러 없음.

- [ ] **Step 4: 회귀 확인 — 백엔드 전체 테스트가 여전히 통과하는지**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -q`
Expected: 실패 0(이 태스크는 `desktop/app.py`만 건드려 백엔드 회귀는 원래 없어야 하지만, 임포트 경로 실수를 조기에 잡기 위해 확인)

- [ ] **Step 5: 커밋**

```bash
git add desktop/app.py
git commit -m "feat(desktop): RUNTIME-1 app.py — VAULT.set_pending_hook에 notify.build_notifier 연결

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## 수동 검증 (이 플랜의 자동화 범위 밖 — 실행 파일 재빌드·실기기 확인은 사용자 몫)

아래는 코드로 자동 검증할 수 없는 부분이다. Task 1~6이 전부 끝난 뒤, 다음 절차로 직접 확인한다(README·설계 스펙의 "테스트" 절과 동일):

1. `cd desktop && python setup.py build` 로 `KeyLens.exe` 재빌드.
2. exe 실행 → 마스터 비밀번호로 잠금 해제.
3. 다른 터미널에서 미등록 경로로 SDK 요청 시뮬레이션:
   `curl -X POST http://localhost:8765/sdk/env -H "Content-Type: application/json" -d "{\"project\":\"테스트\",\"path\":\"/tmp/test\"}"`
4. 확인 항목: 작업표시줄 아이콘 깜빡임 · OS 토스트 표시 · 창이 자동으로 승인 대기 화면으로 전환.
5. 승인 대기 화면에서 "허용" 클릭 → 같은 curl 명령 재실행 시 403 대신 `{"values": {...}}` 반환 확인.
6. 사이드바 "승인 대기" 뱃지가 요청 발생 시 나타나고 처리 후 사라지는지 확인.

## Self-Review 메모 (계획 작성자 확인용)

- **스펙 커버리지**: 설계 스펙의 "구성 요소" 표 7행 중 `vault_session.py`(Task 1)·`desktop/notify.py`(Task 5)·`desktop/app.py`(Task 6)·`keylensStore.ts`(Task 3)·`PendingScreen.tsx`(Task 4)·`Sidebar.tsx`(Task 4)·`client.ts`(Task 2)·`App.tsx`(Task 4) 전부 태스크로 매핑됨. "토스트 클릭 콜백에 의존하지 않는다"(핵심 설계 판단)는 Task 5의 `_goto_pending`이 클릭과 무관하게 항상 호출되는 것으로 충족. `/sdk/pending` 등 API 라우트는 이미 구현돼 있어 새 태스크 불필요(확인만 함).
- **플레이스홀더 스캔**: 없음 — 모든 스텝에 완전한 코드·정확한 명령·기대 출력 포함.
- **타입 일관성**: `build_notifier(window, title="KeyLens") -> Callable[[str, str], None]`가 Task 5(정의)·Task 6(호출부, `VAULT.set_pending_hook(notify.build_notifier(window))`) 동일. `sdkApi.pending()/approve()/deny()`가 Task 2(정의)·Task 3(스토어에서 호출) 동일 시그니처. `PendingRequest{id,project,path,requestedAt}`가 Task 2(정의)·Task 3(매핑)·Task 4(렌더링) 동일 필드명.
- **테스트 인프라 판단**: 프론트는 이 프로젝트에 React 컴포넌트/스토어 단위테스트 인프라(@testing-library 등)가 전혀 없다(기존 vitest 4개 파일 전부 순수 로직 테스트, `vite.config.ts`도 `environment: 'node'`). 새 인프라를 이 플랜 하나를 위해 들이는 대신, 기존 관례(수동 브라우저 확인)를 따랐다 — Task 4 Step 5. 백엔드(Task 1)·`desktop/notify.py`(Task 5)는 순수 로직이라 TDD로 커버했다.
