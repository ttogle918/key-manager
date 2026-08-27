# 보관함 프로젝트별 그룹핑 + 서비스 로고 태그 필터 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보관함(VaultScreen) 그룹핑 축을 서비스에서 프로젝트로 뒤집는다 — 프로젝트 섹션(아코디언) 안에
서비스 소그룹, 상단엔 서비스 로고 태그 다중 선택 필터를 추가한다.

**Architecture:** `VaultItem.project`(이미 존재하는 필드)를 1차 그룹 키로 쓴다. 프로젝트 미지정 저장은
백엔드가 등록일(UTC `YYYY-MM-DD`)을 실제 `project` 값으로 채운다. 프론트는 `projectKey(it) =
it.project || it.addedAt` 헬퍼로 그룹핑·필터·`.env` 복사를 전부 일관되게 계산한다. 서비스 로고는
simple-icons(CC0) SVG 6개를 로컬에 커밋해 정적 자산으로 쓴다(런타임 네트워크 요청 없음). 나머지
3종(OpenAI·Slack·AWS)은 simple-icons에서 상표권 이슈로 제거되어 있어 로고 없이 기존 폴백 타일을 쓴다
— Task 4 착수 중 실제 npm 설치로 확인됨, 설계 스펙 작성 당시의 조사 오류.

**Tech Stack:** FastAPI(백엔드), React + TypeScript + Zustand + Tailwind(프론트), simple-icons(빌드
타임 전용 devDependency, 런타임 코드는 import하지 않음).

## Global Constraints

- 새로 만드는 모든 파일 맨 위에 SPDX 헤더 2줄(`[Your Name]` 리터럴 그대로 — 이 레포 전역 관례).
- 이번 작업으로 새 런타임 의존성을 추가하지 않는다 — `simple-icons`는 로고 파일을 한 번 복사해오는
  용도의 devDependency일 뿐, 어떤 런타임 코드도 이 패키지를 import하지 않는다.
- 프론트엔드 검증은 `npx tsc --noEmit` + `npm run lint`(oxlint) + `npm run build` — 이 레포는 React
  컴포넌트/스토어 자동 테스트 인프라가 없다(기존 관례). 순수 로직(`lib/format.ts`, `data/services.ts`)은
  vitest로 검증한다.
- 백엔드 프로젝트 기본값(등록일)은 **UTC** 기준 `YYYY-MM-DD` — 기존 `_now()`(`vault_repo.py`)와
  타임존을 맞춘다.
- `envItems()`(`keylensStore.ts`)·EnvModal·`envCopyAll`·`envDownload`는 **건드리지 않는다** — 이들은
  `projFilter`로 스코프되는 기존 메커니즘 그대로 둔다(이번 개편 후에도 "마지막으로 이동한 프로젝트"가
  `.env` 전체 내보내기 범위로 쓰이는 건 의도된 부작용이며, 빈 문자열 선택 시 "전체 프로젝트"로 리셋됨).
- 새 `envCopyGroup`/`envCopyProject`는 `envItems()`를 재사용하지 않고 `get().vault`를 직접
  `projectKey()`로 필터링한다 — `envItems()`를 재사용하면 지금 보고 있는 프로젝트/서비스 섹션과
  `projFilter`(마지막으로 이동한 프로젝트, 서로 다른 개념)가 어긋날 때 교집합이 비어 조용히 빈
  `.env`가 복사되는 버그가 생긴다.

---

### Task 1: 백엔드 — 프로젝트 미지정 시 등록일을 실제 값으로 저장

**Files:**
- Modify: `backend/app/main.py` (`vault_add`, `vault_update` 근처, 8-11번째 줄 import 블록)
- Test: `backend/tests/test_vault_api.py`

**Interfaces:**
- Consumes: 없음(기존 `VAULT.add_entry`/`VAULT.list_entries`/`VAULT.update_meta` 그대로).
- Produces: `main._today() -> str`(UTC `YYYY-MM-DD`). `vault_add`/`vault_update`의 응답
  `VaultEntryMeta.project`가 항상 비어있지 않은 문자열이 됨(기존 계약 유지, 값 채우기 로직만 추가).

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests/test_vault_api.py`의 기존 `test_add_stores_project_memo`(132번째 줄) 바로 뒤에 추가:

```python
def test_add_without_project_defaults_to_today(vault, monkeypatch):
    """프로젝트 미지정 저장 — 등록일(UTC)이 실제 project 값으로 채워진다(keylens-env 컬렉션명으로도 씀)."""
    monkeypatch.setattr(main, "_today", lambda: "2026-08-27")
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY))
    assert meta.project == "2026-08-27"


def test_add_with_blank_project_also_defaults_to_today(vault, monkeypatch):
    """공백만 있는 project도 미지정과 동일하게 취급."""
    monkeypatch.setattr(main, "_today", lambda: "2026-08-27")
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY, project="   "))
    assert meta.project == "2026-08-27"


def test_update_clearing_project_falls_back_to_created_at_date(vault):
    """PATCH로 project를 비우면 '오늘'이 아니라 그 항목의 등록일(created_at)로 되돌아간다."""
    main.vault_init(VaultInit(password=MASTER))
    meta = main.vault_add(
        VaultEntryCreate(official_name="OPENAI_API_KEY", value=DUMMY, project="블로그")
    )
    updated = main.vault_update(meta.id, VaultEntryUpdate(project=""))
    assert updated.project == meta.created_at[:10]
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run (`backend/`에서): `python -m pytest tests/test_vault_api.py -v -k "defaults_to_today or falls_back_to_created_at"`
Expected: FAIL — `test_add_without_project_defaults_to_today`는 `AttributeError: module 'app.main' has
no attribute '_today'`, 나머지 둘은 `assert '' == '2026-08-27'`류 assertion 실패(project가 빈 문자열로 저장됨).

- [ ] **Step 3: import 추가 + `_today()` 헬퍼 + `vault_add`/`vault_update` 수정**

`backend/app/main.py` 8-11번째 줄:

```python
from __future__ import annotations

import os
from pathlib import Path
```

다음으로 교체:

```python
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
```

`backend/app/main.py`의 `vault_lock`(247-250번째 줄)과 `vault_list`(253-255번째 줄) 사이에 헬퍼 추가:

```python
@app.post("/vault/lock", response_model=VaultStatus)
def vault_lock() -> VaultStatus:
    VAULT.lock()
    return VaultStatus(**VAULT.status())


@app.get("/vault/entries", response_model=list[VaultEntryMeta])
def vault_list() -> list[VaultEntryMeta]:
```

다음으로 교체:

```python
@app.post("/vault/lock", response_model=VaultStatus)
def vault_lock() -> VaultStatus:
    VAULT.lock()
    return VaultStatus(**VAULT.status())


def _today() -> str:
    """프로젝트 미지정 저장의 기본값(UTC) — keylens-env 컬렉션명으로도 그대로 쓰일 수 있다."""
    return datetime.now(timezone.utc).date().isoformat()


@app.get("/vault/entries", response_model=list[VaultEntryMeta])
def vault_list() -> list[VaultEntryMeta]:
```

`vault_add`(258-268번째 줄) 전체를:

```python
@app.post("/vault/entries", response_model=VaultEntryMeta)
def vault_add(body: VaultEntryCreate) -> VaultEntryMeta:
    try:
        eid = VAULT.add_entry(
            service=body.service, kind=body.kind, official_name=body.official_name,
            value=body.value, label=body.label, project=body.project, memo=body.memo,
            expires_at=body.expires_at,
        )
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    return next(m for m in [VaultEntryMeta(**x) for x in VAULT.list_entries()] if m.id == eid)
```

다음으로 교체:

```python
@app.post("/vault/entries", response_model=VaultEntryMeta)
def vault_add(body: VaultEntryCreate) -> VaultEntryMeta:
    project = (body.project or "").strip() or _today()
    try:
        eid = VAULT.add_entry(
            service=body.service, kind=body.kind, official_name=body.official_name,
            value=body.value, label=body.label, project=project, memo=body.memo,
            expires_at=body.expires_at,
        )
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    return next(m for m in [VaultEntryMeta(**x) for x in VAULT.list_entries()] if m.id == eid)
```

`vault_update`(271-281번째 줄) 전체를:

```python
@app.patch("/vault/entries/{entry_id}", response_model=VaultEntryMeta)
def vault_update(entry_id: int, body: VaultEntryUpdate) -> VaultEntryMeta:
    try:
        ok = VAULT.update_meta(
            entry_id, project=body.project, memo=body.memo, expires_at=body.expires_at
        )
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    if not ok:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다")
    return next(m for m in [VaultEntryMeta(**x) for x in VAULT.list_entries()] if m.id == entry_id)
```

다음으로 교체:

```python
@app.patch("/vault/entries/{entry_id}", response_model=VaultEntryMeta)
def vault_update(entry_id: int, body: VaultEntryUpdate) -> VaultEntryMeta:
    project = (body.project or "").strip()
    if not project:
        # project를 비우면 "오늘"이 아니라 그 항목의 등록일로 되돌린다 — 수정 행위 자체가
        # 그룹핑 날짜를 오늘로 밀어버리면 안 되므로.
        current = next((m for m in VAULT.list_entries() if m["id"] == entry_id), None)
        project = current["created_at"][:10] if current else _today()
    try:
        ok = VAULT.update_meta(
            entry_id, project=project, memo=body.memo, expires_at=body.expires_at
        )
    except VaultLocked:
        raise HTTPException(status_code=401, detail="금고가 잠겨 있습니다 — 인증하세요") from None
    if not ok:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다")
    return next(m for m in [VaultEntryMeta(**x) for x in VAULT.list_entries()] if m.id == entry_id)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_vault_api.py -v`
Expected: PASS(기존 케이스 포함 전부 — 특히 `test_update_meta`는 project="새프로젝트"로 값이 있으니
그대로 통과해야 함)

- [ ] **Step 5: 전체 백엔드 회귀 확인**

Run: `python -m pytest -q`
Expected: 전부 PASS(기존 개수 + 신규 3개)

- [ ] **Step 6: 커밋**

```bash
git add backend/app/main.py backend/tests/test_vault_api.py
git commit -m "$(cat <<'EOF'
feat(vault): 프로젝트 미지정 저장 시 등록일을 실제 project 값으로

keylens-env 컬렉션명으로 즉시 쓸 수 있게 화면 표시용이 아니라 실제
DB 값으로 채운다. PATCH로 비우면 "오늘"이 아니라 그 항목의 등록일로
되돌아간다(수정이 그룹핑 날짜를 바꾸면 안 되므로).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: 프론트 — `projectKey()` 헬퍼

**Files:**
- Modify: `frontend/src/lib/format.ts`
- Test: `frontend/src/lib/format.test.ts`

**Interfaces:**
- Consumes: `VaultItem`(`@/types`, 이미 존재).
- Produces: `projectKey(it: VaultItem): string` — Task 3(스토어)·Task 7(VaultScreen)에서 그룹핑·필터·
  `.env` 복사 전부 이 함수로 통일해서 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/lib/format.test.ts` 맨 끝에 추가(기존 `import` 줄도 수정):

```typescript
import { describe, expect, it } from 'vitest'
import { jwtExp, passwordPolicyError, projectKey } from './format'
import type { VaultItem } from '@/types'
```

(기존 `import { jwtExp, passwordPolicyError } from './format'` 줄을 위처럼 교체 — `projectKey` 추가 +
`VaultItem` 타입 import 신설.)

파일 끝에 추가:

```typescript
function makeVaultItem(overrides: Partial<VaultItem> = {}): VaultItem {
  return {
    id: '1',
    service: 'OpenAI',
    type: 'API Key',
    varName: 'OPENAI_API_KEY',
    masked: 'sk-****',
    full: 'sk-dummy',
    addedAt: '2026-08-27',
    project: '',
    context: '',
    memo: '',
    sourceImage: null,
    expiresAt: null,
    history: [],
    meta: {},
    ...overrides,
  }
}

describe('projectKey', () => {
  it('project가 있으면 그대로 쓴다', () => {
    expect(projectKey(makeVaultItem({ project: '블로그' }))).toBe('블로그')
  })

  it('project가 빈 문자열이면 등록일(addedAt)로 대체한다', () => {
    expect(projectKey(makeVaultItem({ project: '', addedAt: '2026-08-27' }))).toBe('2026-08-27')
  })
})
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run (`frontend/`에서): `npx vitest run src/lib/format.test.ts`
Expected: FAIL — `projectKey` is not exported from `./format`

- [ ] **Step 3: `projectKey()` 구현**

`frontend/src/lib/format.ts`의 `import type { VaultItem } from '@/types'` 줄(이미 있음) 바로 아래,
`today()` 함수 정의 앞에 추가:

```typescript
/**
 * 보관함 그룹핑용 프로젝트 키. project 미지정 항목은 등록일로 묶는다 — 백엔드가 새 저장 시
 * 실제 project 값을 등록일로 채워주지만(main.vault_add), 마이그레이션하지 않은 기존 항목은
 * 여전히 project가 빈 문자열일 수 있어 화면에서도 동일 규칙으로 방어한다.
 */
export function projectKey(it: VaultItem): string {
  return it.project || it.addedAt
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `npx vitest run src/lib/format.test.ts`
Expected: PASS(전부)

- [ ] **Step 5: 커밋**

```bash
git add frontend/src/lib/format.ts frontend/src/lib/format.test.ts
git commit -m "$(cat <<'EOF'
feat(vault): projectKey 헬퍼 — 프로젝트 미지정 항목은 등록일로 그룹핑

그룹핑·필터·.env 복사가 전부 이 함수 하나로 프로젝트 키를 계산하게
통일한다(스토어/VaultScreen에서 재사용).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: 프론트 — 스토어 상태/액션(아코디언·서비스 태그 필터·.env 복사)

**Files:**
- Modify: `frontend/src/store/keylensStore.ts`

**Interfaces:**
- Consumes: `projectKey`(Task 2, `@/lib/format`).
- Produces: 상태 `projectOpenOverrides: Record<string, boolean>`, `serviceTagFilter: Set<string>`.
  액션 `expandProject(name: string): void`, `toggleProjectSection(name: string, currentlyOpen:
  boolean): void`, `toggleServiceTag(name: string): void`, `clearServiceTagFilter(): void`,
  `envCopyProject(project: string): void`. 기존 `envCopyGroup(name: string): void`의 시그니처를
  `envCopyGroup(project: string, service: string): void`로 변경(Task 7에서 유일한 호출부를 새
  시그니처로 다시 씀).

- [ ] **Step 1: import에 `projectKey` 추가**

`frontend/src/store/keylensStore.ts` 25번째 줄:

```typescript
import { envText, jwtExp, passwordPolicyError, today } from '@/lib/format'
```

다음으로 교체:

```typescript
import { envText, jwtExp, passwordPolicyError, projectKey, today } from '@/lib/format'
```

- [ ] **Step 2: 상태 필드 추가**

131-135번째 줄:

```typescript
  // 보관함
  vault: VaultItem[]
  search: string
  projFilter: string
  revealed: Record<string, boolean>
  expandedId: string | null
```

다음으로 교체:

```typescript
  // 보관함
  vault: VaultItem[]
  search: string
  projFilter: string
  /** 프로젝트 아코디언 수동 펼침/접힘 오버라이드(이름→열림 여부). 없으면 기본값(가장 최근=열림). */
  projectOpenOverrides: Record<string, boolean>
  /** 상단 서비스 로고 태그 다중 선택 필터(비어있으면 전체 서비스). */
  serviceTagFilter: Set<string>
  revealed: Record<string, boolean>
  expandedId: string | null
```

- [ ] **Step 3: 액션 타입 선언 추가**

237-238번째 줄:

```typescript
  setSearch: (v: string) => void
  setProjFilter: (v: string) => void
```

다음으로 교체:

```typescript
  setSearch: (v: string) => void
  setProjFilter: (v: string) => void
  /** 드롭다운에서 프로젝트 선택 — 그 섹션을 강제로 펼친다(스크롤은 VaultScreen이 처리). */
  expandProject: (name: string) => void
  toggleProjectSection: (name: string, currentlyOpen: boolean) => void
  toggleServiceTag: (name: string) => void
  clearServiceTagFilter: () => void
```

257번째 줄:

```typescript
  envCopyGroup: (name: string) => void
```

다음으로 교체:

```typescript
  /** 한 프로젝트 섹션 안의 특정 서비스만 .env로 복사(project+service 둘 다 일치하는 항목만). */
  envCopyGroup: (project: string, service: string) => void
  /** 한 프로젝트의 모든 서비스를 합쳐 .env로 복사. */
  envCopyProject: (project: string) => void
```

- [ ] **Step 4: 초기 상태값 추가**

344-347번째 줄:

```typescript
    vault: [],
    search: '',
    projFilter: '',
    revealed: {},
```

다음으로 교체:

```typescript
    vault: [],
    search: '',
    projFilter: '',
    projectOpenOverrides: {},
    serviceTagFilter: new Set(),
    revealed: {},
```

- [ ] **Step 5: 액션 구현 — 아코디언/태그 필터**

907-908번째 줄:

```typescript
    setSearch: (v) => set({ search: v }),
    setProjFilter: (v) => set({ projFilter: v }),
```

다음으로 교체:

```typescript
    setSearch: (v) => set({ search: v }),
    setProjFilter: (v) => set({ projFilter: v }),
    expandProject: (name) =>
      set((s) => ({
        projFilter: name,
        projectOpenOverrides: name
          ? { ...s.projectOpenOverrides, [name]: true }
          : s.projectOpenOverrides,
      })),
    toggleProjectSection: (name, currentlyOpen) =>
      set((s) => ({
        projectOpenOverrides: { ...s.projectOpenOverrides, [name]: !currentlyOpen },
      })),
    toggleServiceTag: (name) =>
      set((s) => {
        const next = new Set(s.serviceTagFilter)
        if (next.has(name)) next.delete(name)
        else next.add(name)
        return { serviceTagFilter: next }
      }),
    clearServiceTagFilter: () => set({ serviceTagFilter: new Set() }),
```

- [ ] **Step 6: 액션 구현 — `.env` 복사(프로젝트/프로젝트+서비스)**

`envCopyGroup` 기존 구현(1107-1110번째 줄 부근):

```typescript
    envCopyGroup: async (name) => {
      const items = await withValues(envItems().filter((i) => i.service === name))
      get().copy(envText(items), name + ' 그룹 .env 복사됨')
    },
```

다음으로 교체:

```typescript
    // vault를 직접 필터링한다(envItems()를 재사용하지 않음) — envItems()는 projFilter(드롭다운으로
    // 마지막에 이동한 프로젝트)로 스코프되는데, 이 두 버튼은 지금 렌더링 중인 프로젝트/서비스 섹션
    // 기준이라 서로 다른 개념이다. envItems()를 재사용하면 두 스코프가 어긋날 때(예: A 섹션에서
    // 복사했는데 projFilter는 예전에 이동한 B로 남아있는 경우) 교집합이 비어 조용히 빈 .env가
    // 복사되는 버그가 생긴다.
    envCopyGroup: async (project, service) => {
      const items = await withValues(
        get().vault.filter((i) => projectKey(i) === project && i.service === service),
      )
      get().copy(envText(items), `${project} · ${service} .env 복사됨`)
    },
    envCopyProject: async (project) => {
      const items = await withValues(get().vault.filter((i) => projectKey(i) === project))
      get().copy(envText(items), project + ' 프로젝트 .env 복사됨')
    },
```

- [ ] **Step 7: `resetProto`에 초기화 추가**

1224-1226번째 줄 부근:

```typescript
        search: '',
        projFilter: '',
        revealed: {},
```

다음으로 교체:

```typescript
        search: '',
        projFilter: '',
        projectOpenOverrides: {},
        serviceTagFilter: new Set(),
        revealed: {},
```

- [ ] **Step 8: 타입 검증**

Run (`frontend/`에서): `npx tsc --noEmit`
Expected: 에러 없음(단, `VaultScreen.tsx`가 아직 예전 `envCopyGroup(name)` 1-인자 호출을 쓰고 있어서
이 시점엔 **타입 에러가 남아있는 게 정상** — Task 7에서 VaultScreen.tsx를 고치면 해소된다. 이 스텝은
`keylensStore.ts` 자체의 새 코드에 오타가 없는지만 훑어보는 용도이며, 최종 통과 확인은 Task 8에서 함).

- [ ] **Step 9: 커밋**

```bash
git add frontend/src/store/keylensStore.ts
git commit -m "$(cat <<'EOF'
feat(vault): 프로젝트 아코디언·서비스 태그 필터 스토어 상태/액션

projectOpenOverrides(수동 펼침 오버라이드)·serviceTagFilter(다중
선택)·expandProject(드롭다운 점프)·envCopyProject 추가. 기존
envCopyGroup은 project+service 둘 다 받도록 시그니처 변경 — vault를
직접 projectKey()로 필터링해 projFilter와의 스코프 혼선을 피한다.
호출부(VaultScreen)는 다음 커밋에서 갱신.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: 프론트 — 서비스 로고 SVG 벤더링(simple-icons)

**Files:**
- Modify: `frontend/package.json` (devDependencies·scripts)
- Create: `frontend/scripts/vendor-logos.mjs`
- Create: `frontend/src/assets/logos/{notion,kakao,gcp,ollama,github,stripe}.svg`
  (스크립트 실행 결과물 — 커밋 대상)
- Modify: `THIRD-PARTY-NOTICES.md`

**Interfaces:**
- Consumes: 없음.
- Produces: `frontend/src/assets/logos/*.svg` 6개 파일(Task 5에서 import). OpenAI·Slack·AWS는
  simple-icons에 아이콘 자체가 없어(상표권 이슈로 제거됨) 로고 파일을 만들지 않는다 — Task 5/7에서
  이 세 서비스는 자동으로 기존 컬러 이니셜 타일 폴백을 쓴다.

- [ ] **Step 1: `simple-icons` devDependency 추가**

`frontend/package.json`의 `"devDependencies"` 블록(33번째 줄)에 추가:

```json
  "devDependencies": {
    "@tailwindcss/vite": "^4.3.2",
    "@types/node": "^24.13.2",
    "@types/react": "^19.2.17",
    "@types/react-dom": "^19.2.3",
    "@vitejs/plugin-react": "^6.0.3",
    "oxlint": "^1.71.0",
    "simple-icons": "^16.28.0",
    "tailwindcss": "^4.3.2",
    "typescript": "~6.0.2",
    "vite": "^8.1.1",
    "vitest": "^4.1.9"
  },
```

`"scripts"` 블록(7번째 줄)의 `"vendor:fonts"` 줄 뒤에 추가:

```json
    "vendor:fonts": "node scripts/vendor-fonts.mjs",
    "vendor:logos": "node scripts/vendor-logos.mjs"
```

(마지막 줄이던 `"vendor:fonts"` 뒤에 콤마를 붙이고 새 줄을 추가하는 것 — JSON 문법에 유의.)

Run (`frontend/`에서): `npm install`
Expected: `node_modules/simple-icons`가 생기고 `package-lock.json`에 `simple-icons`가 잠김.

- [ ] **Step 2: 벤더 스크립트 작성**

`frontend/scripts/vendor-logos.mjs`(신규):

```javascript
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * simple-icons(CC0-1.0 — 저작권은 포기되지만 상표권은 각 브랜드사 소유, THIRD-PARTY-NOTICES.md
 * 참고)에서 KeyLens가 쓰는 6개 서비스 로고만 뽑아 src/assets/logos/ 에 커밋 대상 정적 파일로
 * 복사한다. 런타임 코드는 simple-icons를 import하지 않는다(devDependency 전용) — 결과 SVG
 * 파일 6개(수 KB)만 저장소에 커밋하고, tesseract 모델처럼 매 빌드마다 다시 뽑을 필요는 없다.
 * 새 서비스 로고가 필요해지면 LOGOS에 한 줄 추가 후 수동 실행: npm run vendor:logos
 *
 * OpenAI·Slack·AWS는 simple-icons에 아이콘 자체가 없다(브랜드 요청으로 제거됨 —
 * node_modules/simple-icons/DISCLAIMER.md의 "Removal of Brands" 참고). 이 세 서비스는
 * KeyLens에서 로고 없이 기존 컬러 이니셜 타일 폴백을 쓴다(services.ts, 자동).
 */
import { cpSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const src = join(root, 'node_modules', 'simple-icons', 'icons')
const dst = join(root, 'src', 'assets', 'logos')

// KeyLens 서비스 id(backend/knowledge/*.yaml 의 `service:`) → simple-icons slug.
// openai/aws/slack은 simple-icons에 없어(브랜드 요청 제거) 의도적으로 뺐다 — 폴백 타일 사용.
const LOGOS = {
  notion: 'notion',
  kakao: 'kakao',
  gcp: 'googlecloud',
  ollama: 'ollama',
  github: 'github',
  stripe: 'stripe',
}

if (!existsSync(src)) {
  console.error('[vendor-logos] node_modules/simple-icons 없음 — npm install 먼저')
  process.exit(1)
}
mkdirSync(dst, { recursive: true })
for (const [id, slug] of Object.entries(LOGOS)) {
  const from = join(src, `${slug}.svg`)
  if (!existsSync(from)) {
    console.error(`[vendor-logos] icons/${slug}.svg 없음 — simple-icons 버전이 바뀌었을 수 있음`)
    process.exit(1)
  }
  cpSync(from, join(dst, `${id}.svg`))
}
console.log(`[vendor-logos] ${Object.keys(LOGOS).length}개 로고 → src/assets/logos/`)
```

- [ ] **Step 3: 실행해서 실제로 6개가 뽑히는지 확인**

Run (`frontend/`에서): `npm run vendor:logos`
Expected: `[vendor-logos] 6개 로고 → src/assets/logos/` 출력, `frontend/src/assets/logos/`에
`notion.svg, kakao.svg, gcp.svg, ollama.svg, github.svg, stripe.svg` 6개 파일 생성.

만약 `icons/googlecloud.svg 없음` 같은 에러가 나면 simple-icons 버전이 바뀌어 slug가 달라진 것 —
`node_modules/simple-icons/icons/`를 직접 훑어(`ls node_modules/simple-icons/icons | grep -i cloud`
등) 맞는 slug로 `LOGOS`를 고친 뒤 다시 실행.

- [ ] **Step 4: 라이선스 고지 추가**

`THIRD-PARTY-NOTICES.md`의 129-131번째 줄:

```markdown
> OFL 전문: https://openfontlicense.org/

## 백엔드 런타임 (FastAPI 로컬 서버)
```

다음으로 교체:

```markdown
> OFL 전문: https://openfontlicense.org/

## 서비스 로고 아이콘 (frontend, 보관함 서비스 태그)

### simple-icons
- 버전: 16.28.0
- 라이선스: **CC0-1.0**(저작권 전면 포기) — 단, 라이선스 본문 4조 1항에 "상표권·특허권은 이 문서로
  포기·양도되지 않는다"고 명시. 즉 SVG 아이콘의 **저작권만 CC0**이고, Notion·GCP·OpenAI 등 각 로고가
  나타내는 **브랜드 상표권은 여전히 해당 회사 소유**다.
- 출처: https://github.com/simple-icons/simple-icons (npm `simple-icons@16.28.0`)
- 용도: 보관함 화면 상단 "서비스별 필터" 태그의 아이콘(6종: Notion·Kakao·GCP·Ollama·GitHub·Stripe).
  원본 SVG를 수정 없이 `frontend/scripts/vendor-logos.mjs`로 복사해 `frontend/src/assets/logos/*.svg`에
  커밋(빌드타임 devDependency일 뿐 런타임 코드는 import하지 않음 — 런타임 의존성 0).
- **상표 사용 근거(nominative fair use)**: "이 자격증명이 어느 서비스 것인지" 식별하는 지시적 용도로만
  쓴다(로고를 변형·재판매하거나 KeyLens가 해당 회사와 제휴한 것처럼 표시하지 않음). 비밀번호 관리자·
  OAuth 로그인 화면 등에서 서비스 식별용으로 원본 브랜드 마크를 그대로 보여주는 건 업계 보편적 관행이다.
- **OpenAI·Slack·AWS는 이 세트에 없다** — simple-icons가 브랜드 요청으로 해당 아이콘을 완전히
  제거했다(`node_modules/simple-icons/DISCLAIMER.md`의 "Removal of Brands" 참고, `icons/` 폴더에
  파일 자체가 없음 — 다른 slug로 남아있지도 않음). 이 세 서비스는 KeyLens에서 로고 없이 기존 컬러
  이니셜 타일(`SVC_META` 폴백)을 그대로 쓴다 — 별도 대응 불필요, 코드가 이미 그렇게 폴백하도록
  설계돼 있다(Task 5).

## 백엔드 런타임 (FastAPI 로컬 서버)
```

- [ ] **Step 5: 커밋**

```bash
git add frontend/package.json frontend/package-lock.json frontend/scripts/vendor-logos.mjs \
  frontend/src/assets/logos THIRD-PARTY-NOTICES.md
git commit -m "$(cat <<'EOF'
feat(vault): 서비스 로고 SVG 6종 벤더링(simple-icons, CC0)

simple-icons는 로고 파일을 한 번 뽑아오는 devDependency일 뿐 런타임
코드는 import하지 않는다 — 결과 SVG 6개만 커밋. 저작권은 CC0지만
상표권은 각사 소유라 THIRD-PARTY-NOTICES.md에 지시적 사용 근거를
기록. OpenAI·Slack·AWS는 simple-icons에 로고 자체가 없다(브랜드
요청으로 제거됨) — 이 셋은 폴백 타일로 대신한다(Task 5).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: 프론트 — `data/services.ts`에 `SVC_LOGO` 배선

**Files:**
- Modify: `frontend/src/data/services.ts`
- Test: `frontend/src/data/services.test.ts`

**Interfaces:**
- Consumes: `frontend/src/assets/logos/*.svg`(Task 4, 6개뿐 — OpenAI·AWS·Slack은 없음).
- Produces: `SVC_LOGO: Record<string, string>`(표시명 → 로고 URL, `SVC_META`와 동일한 라이브 바인딩
  패턴) — 로고가 없는 서비스는 키 자체가 없다(Task 7에서 폴백 처리). AWS·Slack은 로고가 없는 대신
  `CURATED_META`에 브랜드 색을 큐레이션해서(해시 기반 자동색 대신) 폴백 타일이라도 실제 브랜드
  색으로 보이게 한다 — OpenAI는 이미 기존 `CURATED_META`에 브랜드색이 있어 손댈 필요 없음.

- [ ] **Step 1: 실패하는 테스트 작성**

`frontend/src/data/services.test.ts`의 마지막 `it(...)` 블록(약 65번째 줄, `발급 도움말...` 케이스)
바로 앞에 추가:

```typescript
  it('로고가 있는 6종은 SVC_LOGO가 채워진다', () => {
    reg.applyKnowledge(PAYLOAD)
    expect(reg.SVC_LOGO['Notion']).toBeTruthy()
    expect(reg.SVC_LOGO['GitHub']).toBeTruthy()
    expect(reg.SVC_LOGO['Stripe']).toBeTruthy()
  })

  it('OpenAI는 simple-icons에 로고가 없어 SVC_LOGO 키가 생기지 않는다(폴백 타일 용도)', () => {
    reg.applyKnowledge(PAYLOAD)
    expect(reg.SVC_LOGO['OpenAI']).toBeUndefined()
  })

  it('로고가 없는 서비스는 SVC_LOGO에 키가 생기지 않는다(폴백 타일 용도)', () => {
    reg.applyKnowledge({
      services: [
        {
          service: 'foobar',
          display_name: 'FooBar',
          credentials: [cred('api_key', 'API Key', 'FOOBAR_API_KEY')],
        },
      ],
    })
    expect(reg.SVC_LOGO['FooBar']).toBeUndefined()
  })

  it('AWS·Slack은 로고가 없지만 SVC_META에 브랜드색이 큐레이션돼 있다(해시 자동색 아님)', () => {
    reg.applyKnowledge({
      services: [
        {
          service: 'aws',
          display_name: 'AWS',
          credentials: [cred('access_key_id', 'Access Key ID', 'AWS_ACCESS_KEY_ID')],
        },
        {
          service: 'slack',
          display_name: 'Slack',
          credentials: [cred('bot_token', 'Bot Token', 'SLACK_BOT_TOKEN')],
        },
      ],
    })
    expect(reg.SVC_META['AWS']).toEqual({ tile: 'A', bg: '#FF9900', fg: '#161E2D' })
    expect(reg.SVC_META['Slack']).toEqual({ tile: 'S', bg: '#4A154B', fg: '#FFFFFF' })
    expect(reg.SVC_LOGO['AWS']).toBeUndefined()
    expect(reg.SVC_LOGO['Slack']).toBeUndefined()
  })
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run (`frontend/`에서): `npx vitest run src/data/services.test.ts`
Expected: FAIL — `reg.SVC_LOGO` is undefined(export 자체가 없음), AWS·Slack 색상 케이스는
`toEqual` 불일치(지금은 `autoMeta()` 해시색이 나옴)

- [ ] **Step 3: `CURATED_META`에 AWS·Slack 브랜드색 추가**

`frontend/src/data/services.ts`의 기존 `CURATED_META` 정의:

```typescript
const CURATED_META: Record<string, SvcMeta> = {
  notion: { tile: 'N', bg: '#E7EAEE', fg: '#15181D' },
  kakao: { tile: 'K', bg: '#F2D14B', fg: '#241D00' },
  gcp: { tile: 'G', bg: '#4E8DF5', fg: '#FFFFFF' },
  openai: { tile: 'O', bg: '#17B597', fg: '#03211B' },
  ollama: { tile: 'Ol', bg: '#111418', fg: '#FFFFFF' },
}
```

다음으로 교체(로고 파일이 없는 AWS·Slack도 실제 브랜드색으로 — 해시 기반 자동색 대신):

```typescript
const CURATED_META: Record<string, SvcMeta> = {
  notion: { tile: 'N', bg: '#E7EAEE', fg: '#15181D' },
  kakao: { tile: 'K', bg: '#F2D14B', fg: '#241D00' },
  gcp: { tile: 'G', bg: '#4E8DF5', fg: '#FFFFFF' },
  openai: { tile: 'O', bg: '#17B597', fg: '#03211B' },
  ollama: { tile: 'Ol', bg: '#111418', fg: '#FFFFFF' },
  // simple-icons에 로고 파일이 없는(브랜드 요청으로 제거됨, Task 4 참고) 서비스 — 폴백 타일이라도
  // 해시 기반 자동색(autoMeta) 대신 실제 브랜드 색을 쓴다.
  aws: { tile: 'A', bg: '#FF9900', fg: '#161E2D' },
  slack: { tile: 'S', bg: '#4A154B', fg: '#FFFFFF' },
}
```

- [ ] **Step 4: `SVC_LOGO` 구현**

`frontend/src/data/services.ts` 맨 위 import 블록(1-4번째 줄):

```typescript
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { KnowledgeResponse } from '@/api/types'
import type { Confidence, SvcMeta, TypeOption } from '@/types'
```

다음으로 교체:

```typescript
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import type { KnowledgeResponse } from '@/api/types'
import type { Confidence, SvcMeta, TypeOption } from '@/types'
import gcpLogo from '@/assets/logos/gcp.svg'
import githubLogo from '@/assets/logos/github.svg'
import kakaoLogo from '@/assets/logos/kakao.svg'
import notionLogo from '@/assets/logos/notion.svg'
import ollamaLogo from '@/assets/logos/ollama.svg'
import stripeLogo from '@/assets/logos/stripe.svg'
```

(OpenAI·AWS·Slack은 import하지 않는다 — Task 4에서 확인된 대로 simple-icons에 해당 로고 파일이
없다. `frontend/src/assets/logos/`에 `openai.svg`/`aws.svg`/`slack.svg`가 없는데 이 셋을 import하면
빌드가 그 자리에서 깨진다.)

`SERVICE_BY_ID` 정의(69-75번째 줄) 뒤, `CONSOLE_URL` 정의(78번째 줄) 앞에 추가:

```typescript
/** 서비스 표시명 → 로고 SVG(simple-icons, THIRD-PARTY-NOTICES.md 참고). 없으면 폴백 타일 사용. */
export let SVC_LOGO: Record<string, string> = {
  Notion: notionLogo,
  Kakao: kakaoLogo,
  GCP: gcpLogo,
  Ollama: ollamaLogo,
}
```

`CURATED_META`/`CURATED_ORDER` 정의 사이, `CURATED_ORDER` 선언 뒤에 추가:

```typescript
// 큐레이션 서비스 id → 로고. simple-icons에 실제 파일이 있는 6종만(OpenAI·AWS·Slack 제외 —
// 위 CURATED_META에서 이 셋은 로고 대신 브랜드색 폴백 타일을 쓴다).
const CURATED_LOGO: Record<string, string> = {
  notion: notionLogo,
  kakao: kakaoLogo,
  gcp: gcpLogo,
  ollama: ollamaLogo,
  github: githubLogo,
  stripe: stripeLogo,
}
```

`applyKnowledge()` 함수(116번째 줄 부근) 안, 지역 변수 선언 블록에 `svcLogo` 추가. 기존:

```typescript
export function applyKnowledge(payload: KnowledgeResponse): void {
  const typeMap: Record<string, TypeOption[]> = {}
  const svcMeta: Record<string, SvcMeta> = {}
  const toId: Record<string, string> = {}
```

다음으로 교체:

```typescript
export function applyKnowledge(payload: KnowledgeResponse): void {
  const typeMap: Record<string, TypeOption[]> = {}
  const svcMeta: Record<string, SvcMeta> = {}
  const svcLogo: Record<string, string> = {}
  const toId: Record<string, string> = {}
```

같은 함수 안, `svcMeta[name] = CURATED_META[s.service] ?? autoMeta(name)` 줄 바로 뒤에 추가:

```typescript
    svcMeta[name] = CURATED_META[s.service] ?? autoMeta(name)
    if (CURATED_LOGO[s.service]) svcLogo[name] = CURATED_LOGO[s.service]
```

함수 끝부분, `SVC_META = svcMeta` 줄 뒤에 추가:

```typescript
  SVC_META = svcMeta
  SVC_LOGO = svcLogo
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `npx vitest run src/data/services.test.ts`
Expected: PASS(전부 — 기존 케이스 포함)

- [ ] **Step 6: 커밋**

```bash
git add frontend/src/data/services.ts frontend/src/data/services.test.ts
git commit -m "$(cat <<'EOF'
feat(vault): SVC_LOGO — 서비스 표시명→로고 SVG 라이브 바인딩

CURATED_META와 같은 패턴으로 로고 있는 6종을 커버. 로고 없는
서비스는 SVC_LOGO 키가 안 생겨 컴포넌트가 자연히 폴백 타일로
그린다. AWS·Slack은 simple-icons에 로고 파일 자체가 없어(브랜드
요청 제거) CURATED_META에 실제 브랜드색을 큐레이션해 해시 기반
자동색 대신 쓰게 했다.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: 프론트 — `VaultRow`의 중복 프로젝트 배지 제거

**Files:**
- Modify: `frontend/src/components/vault/VaultRow.tsx`

**Interfaces:**
- Consumes: 없음.
- Produces: 없음(순수 UI 정리 — 프로젝트가 이제 섹션 헤더에 항상 표시되므로 행마다 반복 표시할
  필요가 없어짐).

- [ ] **Step 1: 접힌 행의 프로젝트 배지 제거**

`frontend/src/components/vault/VaultRow.tsx` 47-56번째 줄:

```tsx
        {/* 종류 + 변수명 */}
        <div className="min-w-0">
          <div className="flex items-center gap-[6px] text-[11.5px] text-muted-2">
            {it.project && (
              <span className="max-w-[110px] overflow-hidden text-ellipsis whitespace-nowrap rounded-[4px] border border-[rgba(143,163,191,.22)] bg-[rgba(143,163,191,.1)] px-[6px] py-px text-[10px] font-semibold text-blue-tag">
                {it.project}
              </span>
            )}
            <span className="overflow-hidden text-ellipsis whitespace-nowrap">{it.type}</span>
            {cur?.exposure === 'secret' && <ExposureBadge exposure="secret" />}
          </div>
```

다음으로 교체(프로젝트 배지 삭제 — 이제 프로젝트 섹션 헤더가 항상 보여주므로 행마다 반복할 필요가
없다. "상세 보기"의 프로젝트 편집 입력칸은 그대로 유지):

```tsx
        {/* 종류 + 변수명 */}
        <div className="min-w-0">
          <div className="flex items-center gap-[6px] text-[11.5px] text-muted-2">
            <span className="overflow-hidden text-ellipsis whitespace-nowrap">{it.type}</span>
            {cur?.exposure === 'secret' && <ExposureBadge exposure="secret" />}
          </div>
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/src/components/vault/VaultRow.tsx
git commit -m "$(cat <<'EOF'
refactor(vault): 행 안 프로젝트 배지 제거(섹션 헤더와 중복)

보관함이 프로젝트별로 그룹핑되면서 섹션 헤더가 항상 프로젝트명을
보여준다 — 행마다 또 표시하는 건 중복. 상세 보기의 프로젝트 편집
입력칸은 그대로 유지.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: 프론트 — `VaultScreen` 프로젝트별 그룹핑/아코디언/로고 태그 필터

**Files:**
- Modify: `frontend/src/components/screens/VaultScreen.tsx` (전체 재작성)

**Interfaces:**
- Consumes: `projectKey`(Task 2), `expandProject`/`toggleProjectSection`/`toggleServiceTag`/
  `clearServiceTagFilter`/`envCopyProject`/`envCopyGroup(project, service)`(Task 3), `SVC_LOGO`
  (Task 5).
- Produces: 없음(최상위 화면 컴포넌트).

- [ ] **Step 1: 전체 파일 교체**

`frontend/src/components/screens/VaultScreen.tsx` 전체를 다음으로 교체:

```tsx
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { SERVICE_ORDER, SVC_LOGO, SVC_META } from '@/data/services'
import { expiryInfo, projectKey } from '@/lib/format'
import { syncRelayConfigured } from '@/lib/syncRelay'
import { useKeylens } from '@/store/keylensStore'
import { useProjectNames } from '@/store/selectors'
import { VaultRow } from '@/components/vault/VaultRow'
import type { VaultItem } from '@/types'

/** 화면 2: 조회 대시보드(보관함) — 프로젝트별 아코디언, 안은 서비스 소그룹. */
export function VaultScreen() {
  const s = useKeylens()
  const projectNames = useProjectNames()
  const { vault, search, projFilter, locked, serviceTagFilter, projectOpenOverrides } = s

  const q = search.trim().toLowerCase()
  const matchSearch = (it: VaultItem) =>
    !q ||
    it.varName.toLowerCase().includes(q) ||
    it.type.toLowerCase().includes(q) ||
    it.service.toLowerCase().includes(q) ||
    (it.memo || '').toLowerCase().includes(q) ||
    (it.context || '').toLowerCase().includes(q) ||
    (it.project || '').toLowerCase().includes(q)
  const matchServiceTag = (it: VaultItem) =>
    serviceTagFilter.size === 0 || serviceTagFilter.has(it.service)
  const filterActive = q.length > 0 || serviceTagFilter.size > 0

  // 만료 임박(≤14일)·만료 항목을 각 소그룹 상단으로. 그 외는 기존 순서 유지(TRUST-2).
  const urgency = (v: VaultItem): number => {
    const e = expiryInfo(v.expiresAt)
    return e && (e.expired || e.days <= 14) ? e.days : Infinity
  }

  const byProject = new Map<string, VaultItem[]>()
  vault
    .filter((it) => matchSearch(it) && matchServiceTag(it))
    .forEach((it) => {
      const key = projectKey(it)
      const arr = byProject.get(key)
      if (arr) arr.push(it)
      else byProject.set(key, [it])
    })

  const projectGroups = Array.from(byProject.entries())
    .map(([name, items]) => ({
      name,
      latest: items.reduce((max, it) => (it.addedAt > max ? it.addedAt : max), ''),
      services: SERVICE_ORDER.map((svc) => ({
        name: svc,
        meta: SVC_META[svc],
        items: items.filter((it) => it.service === svc).sort((a, b) => urgency(a) - urgency(b)),
      })).filter((g) => g.items.length > 0),
    }))
    .sort((a, b) => (a.latest < b.latest ? 1 : a.latest > b.latest ? -1 : 0))

  const vaultEmpty = vault.length === 0
  const noMatches = vault.length > 0 && projectGroups.length === 0

  return (
    <div className="mx-auto max-w-[880px] px-8 pb-[90px] pt-[44px] [animation:klFadeUp_.35s_ease]">
      {/* 헤더 */}
      <div className="mb-[18px] flex flex-wrap items-center gap-[10px]">
        <div className="min-w-[170px] flex-1">
          <h1 className="m-0 text-[20px] font-bold tracking-[-.015em]">보관함</h1>
          <div className="mt-1 text-[12.5px] text-faint-2">
            {vault.length}개 자격증명 · AES-256-GCM으로 암호화되어 이 기기에만 보관
          </div>
        </div>
        <select
          value={projFilter}
          onChange={(e) => {
            const name = e.target.value
            s.expandProject(name)
            if (name) {
              requestAnimationFrame(() => {
                document
                  .getElementById(`vault-project-${name}`)
                  ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
              })
            }
          }}
          className="max-w-[170px] cursor-pointer rounded-lg border border-border bg-surface px-[10px] py-[9px] text-[12.5px] text-fg-soft outline-none"
        >
          <option value="">프로젝트로 이동</option>
          {projectNames.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <input
          value={search}
          onChange={(e) => s.setSearch(e.target.value)}
          placeholder="변수명·프로젝트·메모 검색"
          className="w-[180px] rounded-lg border border-border bg-surface px-3 py-[9px] text-[12.5px] text-fg outline-none focus:border-[rgba(62,207,142,.55)]"
        />
        <button
          type="button"
          onClick={s.openEnv}
          title=".env 파일로 내보내기"
          className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] font-mono text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          .env 내보내기
        </button>
        <button
          type="button"
          onClick={s.exportVault}
          title="암호화된 금고 전체를 파일로 내보내기(다른 기기로 이동·백업)"
          className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          금고 내보내기
        </button>
        <button
          type="button"
          onClick={s.openSync}
          title="다른 기기에서 내보낸 금고 파일 가져오기"
          className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
        >
          가져오기
        </button>
        {syncRelayConfigured && (
          <button
            type="button"
            onClick={s.openEmailSync}
            title="금고 값은 암호화한 채로 이메일로 다른 기기에 전달(서비스명 등 메타데이터는 평문 포함)"
            className="cursor-pointer rounded-lg border border-border bg-surface px-3 py-[9px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
          >
            이메일로 내보내기
          </button>
        )}
        <button
          type="button"
          onClick={locked ? s.gotoLockScreen : s.lockNow}
          className="flex items-center gap-2 rounded-lg px-[14px] py-[9px] text-[12.5px] font-bold hover:brightness-110"
          style={{
            background: locked ? '#3ECF8E' : '#13161B',
            color: locked ? '#05231A' : '#C7CDD6',
            border: `1px solid ${locked ? '#3ECF8E' : '#232931'}`,
          }}
        >
          <span
            className="size-[7px] flex-none rounded-full"
            style={{ background: locked ? '#E3B341' : '#3ECF8E' }}
          />
          {locked ? '잠금 해제' : '잠그기'}
        </button>
      </div>

      {/* 서비스 로고 태그 필터 */}
      {!vaultEmpty && (
        <div className="mb-4 flex flex-wrap items-center gap-[6px]">
          {SERVICE_ORDER.map((name) => {
            const active = serviceTagFilter.has(name)
            const logo = SVC_LOGO[name]
            const meta = SVC_META[name]
            return (
              <button
                key={name}
                type="button"
                onClick={() => s.toggleServiceTag(name)}
                title={name}
                aria-pressed={active}
                className="flex size-8 cursor-pointer items-center justify-center rounded-full border transition-[border-color,box-shadow]"
                style={{
                  borderColor: active ? '#3ECF8E' : 'rgba(255,255,255,.08)',
                  boxShadow: active ? '0 0 0 1px #3ECF8E' : 'none',
                  background: meta?.bg ?? '#232931',
                }}
              >
                {logo ? (
                  <img src={logo} alt="" className="size-4" />
                ) : (
                  <span className="text-[10px] font-extrabold" style={{ color: meta?.fg }}>
                    {meta?.tile}
                  </span>
                )}
              </button>
            )
          })}
          {serviceTagFilter.size > 0 && (
            <button
              type="button"
              onClick={s.clearServiceTagFilter}
              className="cursor-pointer rounded-[6px] border border-border bg-none px-[9px] py-1 text-[11px] font-semibold text-faint hover:border-border-strong hover:text-fg-soft"
            >
              태그 해제
            </button>
          )}
        </div>
      )}

      {/* 잠금 배너 */}
      {locked && (
        <div className="mb-4 flex items-center gap-3 rounded-[10px] border border-border bg-surface px-4 py-[13px] [animation:klFade_.2s]">
          <div className="flex size-[26px] flex-none items-center justify-center rounded-full border-[1.5px] border-border-strong">
            <div className="relative size-[7px] rounded-full border-[1.5px] border-muted-2">
              <div className="absolute left-1/2 top-[6px] h-[5px] w-[2px] -translate-x-1/2 bg-muted-2" />
            </div>
          </div>
          <div className="flex-1 text-[12.5px] text-muted">
            보관함이 잠겨 있습니다 — 값 표시·복사·내보내기가 비활성화되어 있어요.
          </div>
          <button
            type="button"
            onClick={s.gotoLockScreen}
            className="flex-none cursor-pointer rounded-[7px] border-none bg-mint px-[14px] py-2 text-[12px] font-bold text-on-mint hover:brightness-[1.08]"
          >
            잠금 해제
          </button>
        </div>
      )}

      {/* 빈 상태 */}
      {vaultEmpty && (
        <div className="rounded-[14px] border-[1.5px] border-dashed border-border px-6 py-16 text-center">
          <div className="mx-auto flex size-12 items-center justify-center rounded-full border-[1.5px] border-border-strong bg-surface">
            <div className="relative size-[11px] rounded-full border-2 border-faint-2">
              <div className="absolute left-1/2 top-[10px] h-[7px] w-[3px] -translate-x-1/2 bg-faint-2" />
            </div>
          </div>
          <div className="mt-4 text-[15px] font-semibold">아직 저장된 자격증명이 없어요</div>
          <div className="mt-[6px] text-[12.5px] text-faint-2">
            스크린샷을 던지면 무엇인지 알아서 분류해 드립니다.
          </div>
          <button
            type="button"
            onClick={s.goInput}
            className="mt-5 cursor-pointer rounded-lg border-none bg-mint px-[18px] py-[10px] text-[13px] font-bold text-on-mint hover:brightness-[1.08]"
          >
            스크린샷 분석하러 가기
          </button>
        </div>
      )}

      {noMatches && (
        <div className="py-12 text-center text-[13px] text-faint-2">조건에 맞는 항목이 없습니다.</div>
      )}

      {/* 프로젝트별 그룹(아코디언) */}
      {projectGroups.map((pg, idx) => {
        const isOpen = (projectOpenOverrides[pg.name] ?? idx === 0) || filterActive
        const itemCount = pg.services.reduce((n, g) => n + g.items.length, 0)
        return (
          <section
            key={pg.name}
            id={`vault-project-${pg.name}`}
            className="mb-4 overflow-hidden rounded-xl border border-line bg-panel"
          >
            <header className="flex items-center gap-[10px] border-b border-line bg-panel-head px-4 py-[11px]">
              <button
                type="button"
                onClick={() => s.toggleProjectSection(pg.name, isOpen)}
                className="flex flex-1 cursor-pointer items-center gap-[10px] border-none bg-none p-0 text-left"
              >
                <span
                  className="text-[11px] text-faint transition-transform"
                  style={{ transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}
                >
                  ▸
                </span>
                <span className="text-[13.5px] font-semibold">{pg.name}</span>
                <span className="text-[11.5px] text-dim">{itemCount}개</span>
              </button>
              <button
                type="button"
                onClick={() => s.envCopyProject(pg.name)}
                title="이 프로젝트 전체를 .env 형식으로 복사"
                className="cursor-pointer rounded-[6px] border border-border bg-none px-[9px] py-1 font-mono text-[10.5px] font-semibold text-faint hover:border-border-strong hover:text-fg-soft"
              >
                .env 복사
              </button>
            </header>
            {isOpen &&
              pg.services.map((g) => (
                <div key={g.name}>
                  <div className="flex items-center gap-[8px] border-t border-[#14181E] bg-[#0F1216] px-4 py-[7px]">
                    <div
                      className="flex size-[18px] flex-none items-center justify-center rounded-[5px] text-[10px] font-extrabold"
                      style={{ background: g.meta.bg, color: g.meta.fg }}
                    >
                      {g.meta.tile}
                    </div>
                    <span className="text-[11.5px] font-semibold text-muted-2">{g.name}</span>
                    <span className="text-[10.5px] text-dim">{g.items.length}개</span>
                    <button
                      type="button"
                      onClick={() => s.envCopyGroup(pg.name, g.name)}
                      title="이 서비스만 .env 형식으로 복사"
                      className="ml-auto cursor-pointer rounded-[6px] border border-border bg-none px-[8px] py-[2px] font-mono text-[10px] font-semibold text-faint hover:border-border-strong hover:text-fg-soft"
                    >
                      .env 복사
                    </button>
                  </div>
                  {g.items.map((it) => (
                    <VaultRow key={it.id} it={it} />
                  ))}
                </div>
              ))}
          </section>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: 타입/린트/빌드 검증**

Run (`frontend/`에서):
```bash
npx tsc --noEmit
npm run lint
npm run build
```
Expected: 셋 다 에러 없이 통과(Task 3 Step 8에서 남아있던 `envCopyGroup` 시그니처 불일치가 이제 해소됨).

- [ ] **Step 3: 커밋**

```bash
git add frontend/src/components/screens/VaultScreen.tsx
git commit -m "$(cat <<'EOF'
feat(vault): 보관함을 프로젝트별 아코디언으로 재구성 + 서비스 로고 태그 필터

최상위 그룹을 서비스→프로젝트로 전환(서비스는 소그룹). 최근
프로젝트만 기본 펼침, 검색/서비스 태그 필터 일치 시 자동 펼침.
"전체 프로젝트" 드롭다운은 필터가 아니라 해당 섹션으로 스크롤+펼침
용도로 재활용. 상단에 서비스 로고 태그(다중 선택, 호버 시 이름
표시) 추가.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: 전체 검증 + 수동 브라우저 확인

**Files:** 없음(검증 전용 태스크).

**Interfaces:** 없음.

- [ ] **Step 1: 백엔드 전체 회귀**

Run (`backend/`에서): `python -m pytest -q`
Expected: 전부 PASS.

- [ ] **Step 2: 프론트 전체 회귀**

Run (`frontend/`에서):
```bash
npx tsc --noEmit
npm run lint
npm run test
npm run build
```
Expected: 넷 다 에러 없이 통과.

- [ ] **Step 3: 수동 브라우저 확인**

`node scripts/dev.mjs`(레포 루트)로 백/프론트 동시 기동 후:

1. 보관함에 프로젝트를 지정하지 않고 스크린샷 하나를 저장 → 새 프로젝트 섹션 제목이 오늘 날짜
   (`YYYY-MM-DD`)로 뜨는지 확인.
2. 기존에 프로젝트를 지정해 저장해둔 항목이 있다면(예: "블로그") 그 이름으로 별도 섹션이 뜨는지 확인.
3. 가장 최근 저장한 프로젝트 섹션만 펼쳐져 있고 나머지는 접혀 있는지, 접힌 제목을 클릭하면 펼쳐지고
   여러 개를 동시에 펼쳐둘 수 있는지 확인.
4. 검색창에 특정 변수명을 입력했을 때 접혀 있던 다른 프로젝트 섹션이 자동으로 펼쳐지는지, 검색어를
   지우면 원래(최근 프로젝트만 펼침) 상태로 돌아가는지 확인.
5. 상단 서비스 로고 태그를 클릭 — Notion·Kakao·GCP·Ollama·GitHub·Stripe는 실제 로고 이미지가,
   OpenAI·AWS·Slack은 각 브랜드색 폴백 이니셜 타일(O/A/S)이 보이는지 확인. 여러 개를 동시에
   선택했을 때 AND가 아니라 OR로(선택한 서비스들 전부) 걸러지는지 확인. 태그에 마우스를 올렸을 때
   "Notion", "GCP", "AWS" 같은 이름이 툴팁으로 뜨는지 확인(로고든 폴백 타일이든 동일).
6. "프로젝트로 이동" 드롭다운에서 프로젝트를 선택하면 그 섹션으로 스크롤되고 펼쳐지는지 확인.
7. 프로젝트 섹션 헤더의 ".env 복사"를 눌러 클립보드에 그 프로젝트 전체가 복사되는지, 서비스 소그룹
   헤더의 ".env 복사"는 그 프로젝트의 그 서비스만 복사되는지 확인(다른 프로젝트/서비스 값이 섞여
   들어가지 않아야 함).
8. 항목 하나를 펼쳐 "프로젝트" 입력칸을 지우고 포커스를 벗어나면(디바운스 저장 후 목록이 갱신되면)
   그 항목이 원래 등록일 섹션으로 다시 들어가는지 확인.

- [ ] **Step 4: 문제 없으면 최종 보고**

위 8개 확인 항목이 전부 기대대로 동작하면 이 플랜은 완료. 이상이 있으면 어느 스텝에서 어긋났는지
기록하고 해당 Task로 돌아가 수정.
