<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# 금고 완전 초기화(VAULT-RESET) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 교육·공용 PC에서 버튼 하나(+ 마스터 비밀번호 재확인)로 금고를 완전히 비우고 "초기화 안 됨"
상태로 되돌리는 기능을 구현한다.

**Architecture:** 백엔드는 `vault_repo.py`가 이미 쓰는 `DELETE FROM entries/meta/access_log` 패턴
(`replace_with_bundle` 참고)을 재사용해 `reset_vault()`를 신설하고, `sdk_project_dirs`·
`sdk_pending_requests`도 함께 지운다. 인증은 `change_password`와 동일하게 세션 unlock 여부와 무관하게
제공된 비밀번호를 `vault_repo.unlock()`으로 독립 검증한다. 프론트는 사이드바의 기존 "프로토타입 데이터
초기화" 버튼을 실제 API를 호출하는 확인 모달로 교체하고, 성공 시 기존 `resetProto`의 화면 리셋 로직을
재사용한다.

**Tech Stack:** FastAPI(백엔드), React + TypeScript + Zustand(프론트) — 기존 스택 그대로, 새 의존성 0.

## Global Constraints

- 새로 만드는 모든 파일 맨 위에 SPDX 헤더 2줄(`[Your Name]` 리터럴 그대로) — 이번 계획은 기존 파일만
  수정하므로 해당 사항 없음(새 파일 없음).
- 새 런타임 의존성을 추가하지 않는다.
- 백엔드 테스트는 httpx/`TestClient`를 쓰지 않는다 — 라우트 함수를 직접 호출한다
  (`backend/tests/test_vault_api.py`의 기존 패턴).
- 프론트엔드 검증은 `npx tsc --noEmit -p tsconfig.app.json`(주의: 맨 `npx tsc --noEmit`은 이 레포의
  루트 tsconfig.json이 project-references 솔루션 파일이라 조용히 아무것도 검사하지 않는다) +
  `npm run lint`(oxlint) + `npm run build` — 이 레포는 React 컴포넌트 자동 테스트 인프라가 없다(기존
  관례, 새로 만들지 않는다).
- `/vault/reset`은 `change_password`와 동일하게 세션의 `_require_key()`(unlock 여부) 게이트를 두지
  않는다 — 제공된 비밀번호 자체의 검증만으로 인증한다. rate-limit(지수 백오프)도 `change_password`와
  마찬가지로 이번 범위에 넣지 않는다(기존 동일 클래스 엔드포인트와의 일관성 우선).
- `vault.db` 파일 자체는 삭제하지 않는다 — 기존 DELETE SQL 재사용만.

---

### Task 1: 백엔드 — `reset_vault()` + `VaultService.reset()` + `POST /vault/reset`

**Files:**
- Modify: `backend/app/vault_repo.py` (파일 끝에 함수 추가)
- Modify: `backend/app/vault_session.py` (`change_password` 메서드 뒤에 추가)
- Modify: `backend/app/main.py` (`vault_change_password` 엔드포인트 뒤에 추가)
- Test: `backend/tests/test_vault_api.py`

**Interfaces:**
- Consumes: 없음(기존 `vault_repo.unlock`·`crypto.DecryptError`·`VaultStatus`·`VaultPassword` 모델
  재사용).
- Produces: `vault_repo.reset_vault(conn: sqlite3.Connection) -> None`.
  `VaultService.reset(password: str) -> None`(틀린 비번 → `crypto.DecryptError`, 미초기화 금고 →
  `ValueError`, 리셋 후 `self.lock()`으로 세션도 잠금).
  `POST /vault/reset`(body: `VaultPassword`, response: `VaultStatus`) — 401(틀린 비번)/409(미초기화).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_vault_api.py`의 기존 `test_update_meta`(142-148번째 줄) 뒤에 추가:

```python
def test_reset_wrong_password_401_data_intact(vault):
    """틀린 비밀번호로 reset 시도 → 401, 기존 항목 무손상."""
    main.vault_init(VaultInit(password=MASTER))
    main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    with pytest.raises(HTTPException) as e:
        main.vault_reset(VaultPassword(password="wrong password"))
    assert e.value.status_code == 401
    assert len(main.vault_list()) == 1


def test_reset_uninitialized_vault_409(vault):
    """애초에 초기화 안 된 금고에 reset 시도 → 409."""
    with pytest.raises(HTTPException) as e:
        main.vault_reset(VaultPassword(password=MASTER))
    assert e.value.status_code == 409


def test_reset_succeeds_and_uninitializes(vault):
    """올바른 비밀번호로 reset → 성공 후 vault_status가 미초기화를 반환, 세션도 잠김."""
    main.vault_init(VaultInit(password=MASTER))
    main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    result = main.vault_reset(VaultPassword(password=MASTER))
    assert result.initialized is False
    assert result.unlocked is False
    st = main.vault_status()
    assert st.initialized is False


def test_reset_then_reinit_works(vault):
    """reset 후 같은(또는 다른) 비밀번호로 다시 init 가능 — 파일이 아니라 데이터만 지워짐."""
    main.vault_init(VaultInit(password=MASTER))
    main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    main.vault_reset(VaultPassword(password=MASTER))
    st = main.vault_init(VaultInit(password=MASTER))
    assert st.initialized is True
    assert main.vault_list() == []  # 이전 항목 완전히 사라짐


def test_reset_clears_sdk_project_dirs(vault):
    """SDK 디렉토리 사전등록(RUNTIME-1)도 reset 대상 — 공용 PC에 이전 사용자 승인 흔적이 안 남아야 함."""
    main.vault_init(VaultInit(password=MASTER))
    vault.add_project_dir("블로그", "/home/user/blog")
    assert vault.list_project_dirs("블로그") != []
    main.vault_reset(VaultPassword(password=MASTER))
    main.vault_init(VaultInit(password=MASTER))
    assert vault.list_project_dirs("블로그") == []
```

`backend/tests/test_vault_api.py` 8-15번째 줄의 import 블록:

```python
from app.models import (
    VaultChangePassword,
    VaultEntryCreate,
    VaultEntryUpdate,
    VaultInit,
    VaultPassword,
    VaultRotate,
)
```

다음으로 교체(변경 없음 — `VaultPassword`는 이미 import돼 있으므로 이 스텝은 실제로는 수정할 게
없다는 걸 확인하는 용도. 만약 없다면 추가할 것).

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run (`backend/`에서, **반드시 이 venv의 python 사용** — 시스템 PATH의 `python`엔 이 프로젝트 의존성이
없다): `.venv/Scripts/python.exe -m pytest tests/test_vault_api.py -v -k reset`
Expected: FAIL — `AttributeError: module 'app.main' has no attribute 'vault_reset'`

- [ ] **Step 3: `vault_repo.reset_vault()` 구현**

`backend/app/vault_repo.py` 파일 끝(496번째 줄, `change_password` 함수 뒤)에 추가:

```python


def reset_vault(conn: sqlite3.Connection) -> None:
    """금고를 완전히 비우고 미초기화 상태로 되돌린다(원자적).

    항목·메타(마스터 비밀번호 검증기·KDF 파라미터)·감사이력·SDK 디렉토리 승인 기록(RUNTIME-1)까지
    전부 삭제한다. meta 행이 사라지면 is_initialized()가 자동으로 False가 된다. vault.db 파일 자체는
    남는다(같은 파일에 다시 /vault/init 가능) — 교육·공용 PC에서 다음 사용자에게 이전 사용자의 흔적을
    남기지 않기 위한 용도(VAULT-RESET).
    """
    try:
        conn.execute("DELETE FROM access_log")
        conn.execute("DELETE FROM entries")
        conn.execute("DELETE FROM meta")
        conn.execute("DELETE FROM sdk_project_dirs")
        conn.execute("DELETE FROM sdk_pending_requests")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

- [ ] **Step 4: `VaultService.reset()` 구현**

`backend/app/vault_session.py`의 `change_password` 메서드(286-292번째 줄):

```python
    def change_password(self, old_password: str, new_password: str) -> None:
        conn = self._conn()
        try:
            vault_repo.change_password(conn, old_password, new_password)
        finally:
            conn.close()
        self.lock()  # 변경 후 재인증 요구
```

다음 줄(빈 줄 하나 뒤, `# ── RUNTIME-1: SDK 접근 관리 ──` 주석 앞)에 추가:

```python
    def reset(self, password: str) -> None:
        """비밀번호를 재검증한 뒤 금고를 완전히 비우고 미초기화 상태로 되돌린다(VAULT-RESET).

        change_password와 동일하게 세션 unlock 여부와 무관하게 비밀번호 자체로만 인증한다 — 교육·
        공용 PC에서 잠금 해제된 채 방치된 세션만으로 완전 삭제가 가능하면 안 되기 때문.
        - 비밀번호 불일치: crypto.DecryptError
        - 애초에 미초기화 금고: ValueError
        """
        conn = self._conn()
        try:
            vault_repo.unlock(conn, password)  # 검증 전용 — 반환된 키는 쓰지 않고 버림
            vault_repo.reset_vault(conn)
        finally:
            conn.close()
        self.lock()
```

- [ ] **Step 5: `POST /vault/reset` 엔드포인트 추가**

`backend/app/main.py`의 `vault_change_password`(406-418번째 줄):

```python
@app.post("/vault/change-password", response_model=VaultStatus)
def vault_change_password(body: VaultChangePassword) -> VaultStatus:
    try:
        crypto.check_password_strength(body.new_password)
    except crypto.WeakPasswordError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    try:
        VAULT.change_password(body.old_password, body.new_password)
    except crypto.DecryptError:
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다") from None
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return VaultStatus(**VAULT.status())
```

다음 줄(빈 줄 두 개 뒤, `# ── RUNTIME-1: SDK 접근 관리 ──` 주석 앞)에 추가:

```python
@app.post("/vault/reset", response_model=VaultStatus)
def vault_reset(body: VaultPassword) -> VaultStatus:
    """금고 완전 초기화(VAULT-RESET) — 교육·공용 PC용. 비밀번호 재확인 필수, 되돌릴 수 없음."""
    try:
        VAULT.reset(body.password)
    except crypto.DecryptError:
        raise HTTPException(status_code=401, detail="마스터 비밀번호가 올바르지 않습니다") from None
    except ValueError as e:  # 초기화되지 않은 금고
        raise HTTPException(status_code=409, detail=str(e)) from e
    return VaultStatus(**VAULT.status())
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

Run: `.venv/Scripts/python.exe -m pytest tests/test_vault_api.py -v -k reset`
Expected: PASS(5개 전부)

- [ ] **Step 7: 전체 백엔드 회귀 확인**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: 전부 PASS(기존 258 + 신규 5 = 263)

- [ ] **Step 8: 커밋**

```bash
git add backend/app/vault_repo.py backend/app/vault_session.py backend/app/main.py \
  backend/tests/test_vault_api.py
git commit -m "$(cat <<'EOF'
feat(vault): 금고 완전 초기화(VAULT-RESET) — POST /vault/reset

교육·공용 PC 시나리오. change_password와 동일하게 세션 unlock
여부와 무관하게 비밀번호 자체로 재인증. entries/meta/access_log
(기존 replace_with_bundle 패턴 재사용) + RUNTIME-1 SDK 디렉토리
승인 기록까지 전부 삭제 — vault.db 파일은 그대로 남아 재-init
가능.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: 프론트 — API 클라이언트 + 스토어 상태/액션

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/store/keylensStore.ts`

**Interfaces:**
- Consumes: 없음(기존 `vreq`·`VaultApiError`·`vaultErrorText` 재사용).
- Produces: `vaultApi.reset(password: string): Promise<VaultStatus>`. 상태
  `resetVaultOpen: boolean`, `resetVaultPw: string`, `resetVaultErr: string`,
  `resettingVault: boolean`. 액션 `openResetVault(): void`, `closeResetVault(): void`,
  `setResetVaultPw(v: string): void`, `confirmResetVault(): Promise<void>`.

- [ ] **Step 1: `vaultApi.reset` 추가**

`frontend/src/api/client.ts`의 `changePassword`(204-208번째 줄):

```typescript
  changePassword: (oldPassword: string, newPassword: string) =>
    vreq<VaultStatus>('/vault/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }),
}
```

다음으로 교체:

```typescript
  changePassword: (oldPassword: string, newPassword: string) =>
    vreq<VaultStatus>('/vault/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    }),
  reset: (password: string) =>
    vreq<VaultStatus>('/vault/reset', { method: 'POST', body: JSON.stringify({ password }) }),
}
```

- [ ] **Step 2: 상태 필드 추가**

`frontend/src/store/keylensStore.ts`의 149-150번째 줄:

```typescript
  /** 이메일로 내보내기(SYNC-2 재설계) 모달 열림 여부. */
  emailSyncOpen: boolean
```

다음으로 교체:

```typescript
  /** 이메일로 내보내기(SYNC-2 재설계) 모달 열림 여부. */
  emailSyncOpen: boolean
  /** 금고 완전 초기화 확인 모달 상태(VAULT-RESET) — 교육·공용 PC용, 비밀번호 재확인 필수. */
  resetVaultOpen: boolean
  resetVaultPw: string
  resetVaultErr: string
  resettingVault: boolean
```

- [ ] **Step 3: 액션 타입 선언 추가**

287-288번째 줄:

```typescript
  resetProto: () => void
}
```

다음으로 교체:

```typescript
  /** 금고 완전 초기화(VAULT-RESET). */
  openResetVault: () => void
  closeResetVault: () => void
  setResetVaultPw: (v: string) => void
  confirmResetVault: () => Promise<void>

  resetProto: () => void
}
```

- [ ] **Step 4: 초기 상태값 추가**

`emailSyncOpen`의 초기값이 설정되는 줄을 찾아(353번째 줄 부근, `envOpen: false,` 다음) 아래처럼
추가:

```typescript
    envOpen: false,
    syncOpen: false,
    emailSyncOpen: false,
```

다음으로 교체:

```typescript
    envOpen: false,
    syncOpen: false,
    emailSyncOpen: false,
    resetVaultOpen: false,
    resetVaultPw: '',
    resetVaultErr: '',
    resettingVault: false,
```

(정확한 줄 번호는 파일 상태에 따라 다를 수 있음 — `emailSyncOpen: false,` 텍스트로 찾아서 그 뒤에
추가할 것.)

- [ ] **Step 5: 액션 구현**

`resetProto`의 기존 구현(파일 맨 끝 부근, `resetProto: () => {` 로 시작하는 블록) 바로 앞에 추가:

```typescript
    // ── 금고 완전 초기화(VAULT-RESET) ──
    openResetVault: () => set({ resetVaultOpen: true, resetVaultPw: '', resetVaultErr: '' }),
    closeResetVault: () => set({ resetVaultOpen: false, resetVaultPw: '', resetVaultErr: '' }),
    setResetVaultPw: (v) => set({ resetVaultPw: v, resetVaultErr: '' }),
    confirmResetVault: async () => {
      if (get().resettingVault) return
      if (!get().resetVaultPw) {
        set({ resetVaultErr: '마스터 비밀번호를 입력해 주세요.' })
        return
      }
      set({ resettingVault: true, resetVaultErr: '' })
      try {
        await vaultApi.reset(get().resetVaultPw)
        get().resetProto()
      } catch (e) {
        let msg = vaultErrorText(e, '초기화 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요.')
        if (e instanceof VaultApiError && e.status === 401) {
          msg = '마스터 비밀번호가 올바르지 않아요.'
        }
        set({ resettingVault: false, resetVaultErr: msg })
      }
    },
```

**주의**: `confirmResetVault`가 성공 시 호출하는 `get().resetProto()`는 다음 스텝에서 `resetVaultOpen`
등 새 필드도 함께 초기화하도록 확장한다 — 그 전까지는 모달이 화면 전환 후에도 열린 채로 남는
버그가 있는 게 정상(다음 스텝에서 고침, 같은 커밋으로 묶어서 낼 것이므로 중간에 별도로 검증할
필요 없음).

- [ ] **Step 6: `resetProto`가 새 필드도 초기화하도록 확장**

`resetProto`의 기존 구현(`lockPw: '', lockErr: '',` 를 포함하는 줄 부근):

```typescript
        lockPw: '',
        lockErr: '',
        deleteTarget: null,
```

다음으로 교체:

```typescript
        lockPw: '',
        lockErr: '',
        resetVaultOpen: false,
        resetVaultPw: '',
        resetVaultErr: '',
        resettingVault: false,
        deleteTarget: null,
```

- [ ] **Step 7: 타입 검증**

Run (`frontend/`에서): `npx tsc --noEmit -p tsconfig.app.json`
Expected: 에러 없음(단, `Sidebar.tsx`가 아직 예전 `resetProto` 직접 호출을 쓰고 있어도 타입 에러는
안 남 — `resetProto`가 여전히 존재하는 액션이라서. Task 3에서 UI만 갱신하면 됨. 이 태스크에서는
tsc가 clean해야 정상).

- [ ] **Step 8: 커밋**

```bash
git add frontend/src/api/client.ts frontend/src/store/keylensStore.ts
git commit -m "$(cat <<'EOF'
feat(vault): 금고 완전 초기화 스토어 상태/액션 + API 클라이언트

openResetVault/closeResetVault/setResetVaultPw/confirmResetVault
추가. resetProto가 새 모달 상태도 함께 초기화하도록 확장. UI
연결은 다음 커밋에서.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 프론트 — 확인 모달 + 사이드바 버튼 교체

**Files:**
- Modify: `frontend/src/components/modals/Modals.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

**Interfaces:**
- Consumes: `resetVaultOpen`/`resetVaultPw`/`resetVaultErr`/`resettingVault`,
  `openResetVault`/`closeResetVault`/`setResetVaultPw`/`confirmResetVault`(Task 2).
- Produces: `ResetVaultModal`(React 컴포넌트, `Modals.tsx`에서 export).

- [ ] **Step 1: `ResetVaultModal` 작성**

`frontend/src/components/modals/Modals.tsx`의 `DeleteModal` 함수(11-42번째 줄) 바로 뒤에 추가:

```typescript
/** 금고 완전 초기화 확인(VAULT-RESET) — 교육·공용 PC용. 비밀번호 재확인 필수. */
export function ResetVaultModal() {
  const open = useKeylens((s) => s.resetVaultOpen)
  const pw = useKeylens((s) => s.resetVaultPw)
  const err = useKeylens((s) => s.resetVaultErr)
  const resetting = useKeylens((s) => s.resettingVault)
  const setPw = useKeylens((s) => s.setResetVaultPw)
  const cancel = useKeylens((s) => s.closeResetVault)
  const confirm = useKeylens((s) => s.confirmResetVault)

  return (
    <Modal open={open} onClose={cancel} title="금고 완전 초기화" className="w-[380px]">
      <div className="text-[15px] font-bold">금고 완전 초기화</div>
      <p className="mt-2 text-[12.5px] leading-[1.6] text-muted">
        저장된 모든 자격증명·감사 이력·프로젝트 접근 승인 기록이 완전히 삭제됩니다.
        <br />
        <span className="font-semibold text-danger">되돌릴 수 없습니다.</span>
      </p>
      <div className="mt-[14px]">
        <input
          type="password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && confirm()}
          placeholder="마스터 비밀번호"
          autoFocus
          className="w-full rounded-lg border bg-surface-3 px-[11px] py-[9px] text-[13px] text-fg outline-none"
          style={{ borderColor: err ? 'rgba(229,103,92,.55)' : '#232931' }}
        />
        {err && <div className="mt-[9px] text-[12px] text-danger">{err}</div>}
      </div>
      <div className="mt-[18px] flex justify-end gap-2">
        <button
          type="button"
          onClick={cancel}
          className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          취소
        </button>
        <button
          type="button"
          onClick={confirm}
          disabled={resetting}
          className="cursor-pointer rounded-lg border-none bg-danger px-[14px] py-2 text-[12.5px] font-bold text-[#2A0B08] hover:brightness-[1.08] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {resetting ? '초기화 중…' : '완전 초기화'}
        </button>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 2: `App.tsx`에 모달 연결**

`frontend/src/App.tsx`의 19번째 줄:

```typescript
import { DeleteModal, DupModal, EmailSyncModal, EnvModal, RotateModal, SyncModal } from '@/components/modals/Modals'
```

다음으로 교체:

```typescript
import { DeleteModal, DupModal, EmailSyncModal, EnvModal, ResetVaultModal, RotateModal, SyncModal } from '@/components/modals/Modals'
```

`frontend/src/App.tsx`의 97번째 줄(`<ExplainModal />`) 다음 줄에 추가:

```tsx
      <ResetVaultModal />
```

- [ ] **Step 3: 사이드바 버튼 교체**

`frontend/src/components/Sidebar.tsx`의 26번째 줄:

```typescript
  const resetProto = useKeylens((s) => s.resetProto)
```

다음으로 교체:

```typescript
  const openResetVault = useKeylens((s) => s.openResetVault)
```

`frontend/src/components/Sidebar.tsx`의 95-101번째 줄:

```tsx
        <button
          type="button"
          onClick={resetProto}
          className="cursor-pointer border-none bg-none px-2 py-[2px] text-left text-[11px] text-dim-3 hover:text-muted"
        >
          프로토타입 데이터 초기화
        </button>
```

다음으로 교체:

```tsx
        <button
          type="button"
          onClick={openResetVault}
          title="저장된 모든 자격증명을 완전히 삭제하고 초기 상태로 되돌립니다(되돌릴 수 없음)"
          className="cursor-pointer border-none bg-none px-2 py-[2px] text-left text-[11px] text-dim-3 hover:text-danger"
        >
          금고 완전 초기화
        </button>
```

- [ ] **Step 4: 타입/린트/빌드 검증**

Run (`frontend/`에서):
```bash
npx tsc --noEmit -p tsconfig.app.json
npm run lint
npm run build
```
Expected: 셋 다 에러 없이 통과.

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/components/modals/Modals.tsx frontend/src/App.tsx frontend/src/components/Sidebar.tsx
git commit -m "$(cat <<'EOF'
feat(vault): 금고 완전 초기화 확인 모달 + 사이드바 버튼 교체

"프로토타입 데이터 초기화"(화면 상태만 리셋)를 "금고 완전
초기화"(실제 백엔드 데이터 삭제, 비밀번호 재확인)로 교체 —
버튼 라벨이 실제 동작을 정확히 설명하도록.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 전체 검증 + 제출 문서 갱신 + 수동 브라우저 확인

**Files:**
- Modify: `docs/RESULT_REPORT.md` (§8 근처 "금고 완전 초기화(신규 확인된 갭)" 문단)
- Modify: `docs/RESULT_REPORT_제출양식.md` (로드맵 ⑤ 항목)
- Modify 또는 Delete: `docs/superpowers/specs/2026-08-27-vault-full-reset-prompt.md`

**Interfaces:** 없음(검증 + 문서 갱신 전용 태스크).

**⚠️ 주의**: `docs/RESULT_REPORT.md`는 이 계획 작성 시점에 다른(무관한) 진행 중 편집이 있었을 수
있다. 아래 인용된 문장을 그대로 찾을 수 없으면 억지로 끼워맞추지 말고, "금고 완전 초기화"·"원클릭"
키워드로 파일을 검색해 같은 취지의 문단을 찾아 갱신할 것. 못 찾으면 DONE_WITH_CONCERNS로 보고.

- [ ] **Step 1: 백엔드 전체 회귀**

Run (`backend/`에서): `.venv/Scripts/python.exe -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 2: 프론트 전체 회귀**

Run (`frontend/`에서):
```bash
npx tsc --noEmit -p tsconfig.app.json
npm run lint
npm run build
```
Expected: 셋 다 에러 없이 통과(이 레포는 컴포넌트 테스트 인프라가 없어 `npm run test`는 이 기능과
무관 — 그래도 회귀 확인 삼아 돌려도 무방).

- [ ] **Step 3: `docs/RESULT_REPORT.md` 갱신**

파일에서 "금고 완전 초기화(신규 확인된 갭)"으로 시작하는 문단(브리프 작성 시점 기준 아래 내용)을
찾는다:

```
- **금고 완전 초기화(신규 확인된 갭)**: 사이드바의 "프로토타입 데이터 초기화" 버튼은 현재
  **프론트엔드 화면 상태만** 리셋하고 백엔드 `vault.db`의 암호화 항목은 지우지 않는다. 완전
  초기화는 지금은 항목별 삭제 또는 번들 교체(가져오기)로만 가능하다 — 교육·공용 PC 시나리오
  (§1-2 목적 3)를 실제로 지원하는 원클릭 초기화 엔드포인트/버튼은 다음 우선순위로 개발 중이다.
  구현되지 않은 것을 구현됐다고 쓰지 않는다는 원칙(§소감)에 따라 여기 명시한다.
```

다음으로 교체(찾은 실제 문장이 위와 토씨가 다르면 같은 취지로 자연스럽게 고쳐 쓸 것 — 핵심은
"미구현·개발 중" 프레이밍을 "구현 완료" 프레이밍으로 바꾸는 것):

```
- **금고 완전 초기화(구현 완료)**: 사이드바의 "금고 완전 초기화" 버튼(`POST /vault/reset`)이
  마스터 비밀번호 재확인 후 저장된 모든 자격증명·감사 이력·프로젝트 접근 승인 기록을 완전히
  삭제하고 "초기화 안 됨" 상태로 되돌린다 — 교육·공용 PC 시나리오(§1-2 목적 3)를 실제로 지원한다.
```

- [ ] **Step 4: `docs/RESULT_REPORT_제출양식.md` 갱신**

파일에서 로드맵 ⑤ 항목("**원클릭 금고 완전 초기화**"로 시작)을 찾아 "다음 우선순위로 개발 중" 같은
미구현 프레이밍을 "구현 완료"로 자연스럽게 고친다. 84번째 줄 부근의 "한 번에 비우는 원클릭 완전
초기화는 다음 업데이트 목표(로드맵 참고)" 문장도 같은 취지로 "한 번에 비우는 원클릭 완전
초기화(사이드바 '금고 완전 초기화' 버튼)도 지원한다"처럼 구현 완료로 고친다. 41번째 줄 부근의
비슷한 문장도 동일하게.

- [ ] **Step 5: 착수 프롬프트 파일 정리**

`docs/superpowers/specs/2026-08-27-vault-full-reset-prompt.md` 맨 위, `> 대회 제출...` 인용문 줄
바로 뒤에 한 줄 추가:

```markdown
> **구현 완료(2026-08-27)** — `docs/superpowers/specs/2026-08-27-vault-full-reset-design.md`(설계)·
> `docs/superpowers/plans/2026-08-27-vault-full-reset.md`(구현 계획) 참고.
```

(삭제하지 않고 완료 표시만 남긴다 — 나중에 이 기능이 어떤 논의를 거쳐 나왔는지 참고할 수 있도록.)

- [ ] **Step 6: 커밋**

```bash
git add docs/RESULT_REPORT.md docs/RESULT_REPORT_제출양식.md \
  docs/superpowers/specs/2026-08-27-vault-full-reset-prompt.md
git commit -m "$(cat <<'EOF'
docs: 금고 완전 초기화 구현 완료 반영 — 결과보고서·제출양식·프롬프트 표시

VAULT-RESET이 실제로 구현됐으므로 "다음 우선순위로 개발 중" 미구현
프레이밍을 구현 완료로 갱신. 착수 프롬프트 파일은 삭제 대신 완료
표시만 남김(논의 이력 보존).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: 수동 브라우저 확인**

`node scripts/dev.mjs`(레포 루트)로 백/프론트 동시 기동 후:

1. 금고를 만들고(설정 화면) 자격증명 하나를 저장한다.
2. 사이드바에서 "금고 완전 초기화" 클릭 → 확인 모달이 뜨는지, 경고 문구가 보이는지 확인.
3. 빈 비밀번호로 확인 버튼 클릭 → "마스터 비밀번호를 입력해 주세요" 인라인 에러가 뜨는지 확인.
4. 틀린 비밀번호 입력 → "마스터 비밀번호가 올바르지 않아요" 인라인 에러가 뜨는지, 기존 데이터가
   그대로인지(모달 취소 후 보관함에서 확인) 검증.
5. 올바른 비밀번호 입력 → 초기화 성공 → 설정(setup) 화면으로 이동하는지 확인.
6. 같은 비밀번호로 다시 금고를 만들 수 있는지(재-init), 보관함이 비어 있는지 확인.
7. (선택) RUNTIME-1 프로젝트 접근 설정 화면에서 디렉토리를 하나 등록해두고 리셋 후 다시 확인 —
   승인 기록이 사라졌는지.

- [ ] **Step 8: 문제 없으면 최종 보고**

위 7개 확인 항목이 전부 기대대로 동작하면 이 플랜은 완료.
