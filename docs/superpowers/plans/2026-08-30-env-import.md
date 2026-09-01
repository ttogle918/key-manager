<!--
SPDX-FileCopyrightText: 2026 [Your Name]
SPDX-License-Identifier: MIT
-->

# `.env` 가져오기 + 저장 전 인라인 편집 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `.env` 파일을 앱에 끌어다 놓으면 한 화면에서 전 변수를 확인·편집하고 컬렉션 하나로 일괄 저장한다. 원본 변수명을 그대로 지킨다.

**Architecture:** 프론트가 `.env`를 직접 스캔해 **권위 있는 이름·값 목록**을 만들고, 기존 `POST /analyze`는 값으로 매칭해 분류 정보만 얹는다(백엔드 변경 0). 저장은 기존 `vaultApi.add()` 경로를 그대로 쓴다 — 이 기능의 본질은 "`.env`에서 미리 채워진 대량 수동 입력"이다.

**Tech Stack:** React 19 + TypeScript, zustand(스토어), Radix Dialog(`@/components/ui/Modal`), vitest(테스트), Tailwind.

설계 문서: [`docs/superpowers/specs/2026-08-30-env-import-design.md`](../specs/2026-08-30-env-import-design.md)

## Global Constraints

- 모든 새 파일 맨 위에 SPDX 헤더 2줄: `// SPDX-FileCopyrightText: 2026 [Your Name]` / `// SPDX-License-Identifier: MIT`
- **새 의존성 추가 금지.** 이미 있는 것만 쓴다(React·zustand·Radix·Tailwind·vitest).
- 사용자에게 보이는 문자열에 **cp949로 인코딩 불가한 문자를 쓰지 않는다**(em dash `—` 금지, ASCII 하이픈 `-` 사용). 한글 Windows 콘솔에서 죽는다.
- 실제 키·시크릿을 테스트에 넣지 않는다. 더미만(`ghp_` + 반복 문자 등).
- 백엔드는 건드리지 않는다. 이 계획의 모든 변경은 `frontend/` 안에서 끝난다.
- 테스트 실행: `cd frontend && npm test` (vitest run). 단일 파일: `cd frontend && npx vitest run src/lib/envParse.test.ts`
- 타입체크: `cd frontend && npx tsc --noEmit`

## File Structure

**Create**
| 파일 | 책임 |
|---|---|
| `frontend/src/lib/envParse.ts` | `.env` 텍스트 → `{name, value}[]`. 순수 함수, 부수효과 없음 |
| `frontend/src/lib/envParse.test.ts` | 위 파서 단위 테스트 |
| `frontend/src/components/ui/InlineEdit.tsx` | 더블클릭 편집 공용 컴포넌트 |
| `frontend/src/components/modals/EnvImportModal.tsx` | 가져오기 표 + 컬렉션 입력 + 일괄 저장 |

**Modify**
| 파일 | 변경 |
|---|---|
| `frontend/src/types.ts` | `EnvImportRow` 추가, `AnalysisResult`에 `varName` 추가 |
| `frontend/src/store/keylensStore.ts` | 가져오기 상태·액션 추가, `saveAll`의 변수명 우선순위 변경 |
| `frontend/src/components/screens/InputScreen.tsx` | `onDrop`이 텍스트 파일도 받도록 |
| `frontend/src/components/input/ResultCard.tsx` | 변수명 인라인 편집 + 제안 적용 |
| `frontend/src/components/vault/VaultRow.tsx` | 값 더블클릭 → `openRotate` |
| `frontend/src/App.tsx` | `<EnvImportModal />` 마운트 |

---

## Task 1: `.env` 파서

**Files:**
- Create: `frontend/src/lib/envParse.ts`
- Test: `frontend/src/lib/envParse.test.ts`

**Interfaces:**
- Consumes: 없음(독립)
- Produces: `export interface ParsedEnvVar { name: string; value: string }` 와 `export function parseEnv(text: string): ParsedEnvVar[]`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/envParse.test.ts`:

```ts
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * .env 파서 테스트.
 *
 * 가장 중요한 케이스는 "같은 값 다른 이름" 이다 - 백엔드 /analyze 는 값 기준으로 중복을
 * 제거해서 두 변수 중 하나를 조용히 버린다. 이 파서를 따로 두는 이유가 그것이고,
 * 회귀하면 사용자의 변수가 소리 없이 사라진다.
 */
import { describe, expect, it } from 'vitest'
import { parseEnv } from './envParse'

const GH = 'ghp_aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpP1234'

describe('parseEnv', () => {
  it('기본 KEY=VALUE 를 읽는다', () => {
    expect(parseEnv(`FOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('쌍따옴표와 홑따옴표를 벗긴다', () => {
    expect(parseEnv(`A="${GH}"\nB='${GH}'`)).toEqual([
      { name: 'A', value: GH },
      { name: 'B', value: GH },
    ])
  })

  it('export 접두어를 제거한다', () => {
    expect(parseEnv(`export FOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('= 주변 공백을 무시한다', () => {
    expect(parseEnv(`FOO = ${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('인라인 주석을 잘라낸다', () => {
    expect(parseEnv(`FOO=${GH}  # 발급용 메모`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('주석줄과 빈 줄을 건너뛴다', () => {
    expect(parseEnv(`# 주석\n\n   \nFOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('빈 값과 이름 없는 줄을 건너뛴다', () => {
    expect(parseEnv(`EMPTY=\n=${GH}\nFOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('같은 값을 가진 다른 이름 두 줄을 모두 남긴다', () => {
    expect(parseEnv(`FOO=${GH}\nBAR=${GH}`)).toEqual([
      { name: 'FOO', value: GH },
      { name: 'BAR', value: GH },
    ])
  })

  it('같은 이름이 두 번 나오면 나중 줄이 이긴다(.env 관례)', () => {
    expect(parseEnv(`FOO=first\nFOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('따옴표 안의 # 는 주석으로 보지 않는다', () => {
    expect(parseEnv(`FOO="abc#def"`)).toEqual([{ name: 'FOO', value: 'abc#def' }])
  })

  it('여러 줄 값은 첫 줄만 잡는다(문서화된 한계)', () => {
    expect(parseEnv(`FOO="line1\nline2"`)).toEqual([{ name: 'FOO', value: 'line1' }])
  })

  it('CRLF 줄바꿈을 처리한다', () => {
    expect(parseEnv(`FOO=${GH}\r\nBAR=x`)).toEqual([
      { name: 'FOO', value: GH },
      { name: 'BAR', value: 'x' },
    ])
  })

  it('환경변수 이름 형식이 아니면 건너뛴다', () => {
    expect(parseEnv(`나쁜 이름=${GH}\nFOO=${GH}`)).toEqual([{ name: 'FOO', value: GH }])
  })

  it('빈 텍스트는 빈 배열', () => {
    expect(parseEnv('')).toEqual([])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/envParse.test.ts`
Expected: FAIL - `Failed to resolve import "./envParse"`

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/lib/envParse.ts`:

```ts
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * `.env` 텍스트를 {이름, 값} 목록으로 읽는다. 순수 함수 - 부수효과 없음.
 *
 * 왜 프론트에 파서를 두나: 백엔드 /analyze 는 값 기준으로 중복을 제거한다. .env 에서
 * 두 변수가 같은 값을 갖는 건 흔한데(DATABASE_URL / DB_URL), 그러면 변수 하나가 조용히
 * 사라진다. 그래서 이름·값의 권위 있는 목록은 여기서 만들고, /analyze 결과는 분류
 * 정보를 얹는 보강용으로만 쓴다.
 *
 * 지원 범위는 백엔드 파서(stage1)와 맞췄다. 여러 줄 값은 지원하지 않는다 - 시크릿에는
 * 사실상 안 쓰이고, 지원하면 파서가 훨씬 복잡해진다.
 */

export interface ParsedEnvVar {
  name: string
  value: string
}

/** 환경변수 이름으로 인정할 형태(POSIX 관례). */
const NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/

/**
 * 값에서 따옴표를 벗기고 인라인 주석을 잘라낸다.
 * 따옴표로 감싼 값은 그 안의 `#` 을 주석으로 보지 않는다.
 */
function cleanValue(raw: string): string {
  const trimmed = raw.trim()
  const quote = trimmed[0]
  if (quote === '"' || quote === "'") {
    const end = trimmed.indexOf(quote, 1)
    if (end > 0) return trimmed.slice(1, end)
    return trimmed.slice(1) // 닫는 따옴표가 없으면 나머지를 값으로 본다
  }
  const hash = trimmed.indexOf('#')
  return (hash >= 0 ? trimmed.slice(0, hash) : trimmed).trim()
}

export function parseEnv(text: string): ParsedEnvVar[] {
  const byName = new Map<string, string>()
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue

    const eq = line.indexOf('=')
    if (eq <= 0) continue

    let name = line.slice(0, eq).trim()
    if (name.startsWith('export ')) name = name.slice('export '.length).trim()
    if (!NAME_RE.test(name)) continue

    const value = cleanValue(line.slice(eq + 1))
    if (!value) continue

    byName.set(name, value) // 같은 이름이 또 나오면 나중 줄이 이긴다(.env 관례)
  }
  return [...byName].map(([name, value]) => ({ name, value }))
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/envParse.test.ts`
Expected: PASS, 14 tests

- [ ] **Step 5: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: 출력 없음(종료코드 0)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/envParse.ts frontend/src/lib/envParse.test.ts
git commit -m "feat(env-import): .env 텍스트 파서 추가

백엔드 /analyze 는 값 기준으로 중복을 제거해서 같은 값을 가진 두 변수 중 하나를
조용히 버린다. 이름·값의 권위 있는 목록은 프론트에서 만들고 /analyze 는 분류 보강용
으로만 쓴다. 따옴표·export·인라인 주석·CRLF 를 처리하고 여러 줄 값은 지원하지 않는다."
```

---

## Task 2: 더블클릭 인라인 편집 컴포넌트

**Files:**
- Create: `frontend/src/components/ui/InlineEdit.tsx`

**Interfaces:**
- Consumes: 없음
- Produces: `export function InlineEdit(props: { value: string; onCommit: (next: string) => void; displayValue?: string; placeholder?: string; mono?: boolean; ariaLabel: string }): JSX.Element`
  - 더블클릭하면 편집 상태. Enter/blur 로 확정(`onCommit`), Escape 로 취소.
  - `displayValue` 를 주면 **편집 중이 아닐 때 그것을 대신 보여준다**(값 마스킹용). 편집에
    들어가면 항상 `value`(평문)를 고친다.

- [ ] **Step 1: 컴포넌트 작성**

Create `frontend/src/components/ui/InlineEdit.tsx`:

```tsx
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/cn'

/**
 * 더블클릭하면 그 자리에서 고칠 수 있는 텍스트. 편집 중임이 눈에 띄도록 테두리를 진하게
 * 하고 커서를 그 칸에 둔다(자동 포커스 + 전체 선택).
 *
 * Enter 또는 포커스가 빠지면 확정, Escape 면 되돌린다. 키보드만으로도 쓸 수 있게
 * Enter 로도 편집에 들어갈 수 있다(더블클릭은 마우스 사용자용 지름길).
 */
export function InlineEdit({
  value,
  onCommit,
  displayValue,
  placeholder,
  mono = false,
  ariaLabel,
}: {
  value: string
  onCommit: (next: string) => void
  /** 편집 중이 아닐 때 대신 보여줄 문자열(마스킹 등). 없으면 value 를 그대로 보여준다. */
  displayValue?: string
  placeholder?: string
  mono?: boolean
  ariaLabel: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (editing) {
      ref.current?.focus()
      ref.current?.select()
    }
  }, [editing])

  // 바깥에서 값이 바뀌면(예: 제안 적용) 편집 중이 아닐 때 따라간다.
  useEffect(() => {
    if (!editing) setDraft(value)
  }, [value, editing])

  const commit = () => {
    setEditing(false)
    const next = draft.trim()
    if (next !== value) onCommit(next)
  }

  if (editing) {
    return (
      <input
        ref={ref}
        value={draft}
        aria-label={ariaLabel}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit()
          if (e.key === 'Escape') {
            setDraft(value)
            setEditing(false)
          }
        }}
        className={cn(
          'w-full rounded-md bg-surface px-2 py-1 text-[12.5px] text-fg outline-none',
          // 편집 중임을 분명히 - 테두리를 진하게, 링까지
          'border-2 border-[rgba(62,207,142,.75)] ring-2 ring-[rgba(62,207,142,.18)]',
          mono && 'font-mono',
        )}
      />
    )
  }

  return (
    <button
      type="button"
      aria-label={ariaLabel}
      title="더블클릭하면 고칠 수 있어요"
      onDoubleClick={() => setEditing(true)}
      onKeyDown={(e) => {
        if (e.key === 'Enter') setEditing(true)
      }}
      className={cn(
        'w-full cursor-text rounded-md border-2 border-transparent px-2 py-1 text-left',
        'text-[12.5px] text-fg hover:border-border-strong hover:bg-surface',
        mono && 'font-mono',
        !value && 'text-faint-2',
      )}
    >
      {displayValue ?? value ?? ''}
      {!value && !displayValue && (placeholder || '')}
    </button>
  )
}
```

- [ ] **Step 2: `cn` 유틸이 있는지 확인**

Run: `cd frontend && cat src/lib/cn.ts`
Expected: `cn` 을 export 하는 파일이 존재. 없으면 `src/components/ui/Modal.tsx` 의 import 경로를 보고 맞춘다.

- [ ] **Step 3: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: 출력 없음

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/InlineEdit.tsx
git commit -m "feat(ui): 더블클릭 인라인 편집 컴포넌트

편집 중임이 눈에 띄도록 테두리를 진하게 하고 자동 포커스+전체 선택한다.
Enter/blur 확정, Escape 취소. 키보드만으로도 편집에 들어갈 수 있다."
```

---

## Task 3: 타입 + 스토어 상태·액션

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/store/keylensStore.ts`

**Interfaces:**
- Consumes: `parseEnv`, `ParsedEnvVar` (Task 1)
- Produces:
  - `export interface EnvImportRow { id: string; name: string; value: string; checked: boolean; service: string | null; typeLabel: string | null; suggestedName: string | null }`
  - 스토어: `envImportRows: EnvImportRow[]`, `envImportOpen: boolean`, `envImportProject: string`, `envImportBusy: boolean`
  - 액션: `openEnvImport(text: string): Promise<void>`, `closeEnvImport(): void`, `patchEnvRow(id: string, patch: Partial<EnvImportRow>): void`, `setEnvImportProject(v: string): void`, `saveEnvImport(): Promise<void>`

- [ ] **Step 1: 타입 추가**

`frontend/src/types.ts` 의 `AnalysisResult` 인터페이스에 필드 하나를 추가한다(`dupNote` 바로 위):

```ts
  /** 사용자가 정한 환경변수명. 비어 있으면 종류(typeKey)에서 도출한 공식 이름을 쓴다. */
  varName?: string
```

같은 파일 맨 아래에 추가:

```ts
/** `.env` 가져오기 표의 한 줄. 저장 전 상태라 값이 평문으로 들어 있다. */
export interface EnvImportRow {
  id: string
  /** 환경변수명. `.env` 원본 이름이 기본값 - 사용자가 고칠 수 있다. */
  name: string
  value: string
  checked: boolean
  /** /analyze 가 알아본 서비스 id. 못 알아봤으면 null. */
  service: string | null
  /** 종류 라벨(예: "Personal Access Token"). 못 알아봤으면 null. */
  typeLabel: string | null
  /** 지식베이스 공식 이름이 원본과 다를 때만 채워진다 - "제안"으로 보여준다. */
  suggestedName: string | null
}
```

- [ ] **Step 2: 스토어에 상태 추가**

`frontend/src/store/keylensStore.ts` 의 상태 인터페이스에서 `pendingRequests` 선언 근처에 추가:

```ts
  // .env 가져오기
  /** 가져오기 모달 표시 여부. */
  envImportOpen: boolean
  /** 가져오기 표의 줄들(저장 전). */
  envImportRows: EnvImportRow[]
  /** 표 전체에 적용할 컬렉션 이름. 비어 있으면 저장 불가. */
  envImportProject: string
  /** 저장 진행 중(중복 클릭 방지). */
  envImportBusy: boolean
```

액션 선언도 같은 인터페이스에 추가:

```ts
  /** `.env` 텍스트를 파싱해 가져오기 모달을 연다. 분류는 /analyze 로 보강한다. */
  openEnvImport: (text: string) => Promise<void>
  closeEnvImport: () => void
  patchEnvRow: (id: string, patch: Partial<EnvImportRow>) => void
  setEnvImportProject: (v: string) => void
  /** 체크된 줄을 금고에 일괄 저장한다. */
  saveEnvImport: () => Promise<void>
```

초기값(`pendingRequests: []` 근처):

```ts
    envImportOpen: false,
    envImportRows: [],
    envImportProject: '',
    envImportBusy: false,
```

import 에 추가:

```ts
import { parseEnv } from '@/lib/envParse'
```
그리고 기존 `import type { ... } from '@/types'` 목록에 `EnvImportRow` 를 넣는다.

- [ ] **Step 3: 액션 구현**

`loadPending` 액션 바로 앞에 추가:

```ts
    openEnvImport: async (text) => {
      const MAX_BYTES = 1024 * 1024
      const MAX_LINES = 200
      if (text.length > MAX_BYTES) {
        get().showToast('파일이 너무 커요 - 1MB 이하 .env 만 가져올 수 있어요')
        return
      }
      if (text.split(/\r?\n/).length > MAX_LINES) {
        get().showToast('줄이 너무 많아요 - 200줄 이하 .env 만 가져올 수 있어요')
        return
      }
      const parsed = parseEnv(text)
      if (!parsed.length) {
        get().showToast('환경변수를 찾지 못했어요 - KEY=VALUE 형식인지 확인해 주세요')
        return
      }

      // 분류는 보강일 뿐이다. 실패해도 목록은 그대로 보여준다.
      const byValue = new Map<string, { service: string; typeLabel: string; official: string }>()
      try {
        const resp = await analyzeApi({ text })
        for (const it of resp.items) {
          if (!it.service) continue
          byValue.set(it.value, {
            service: it.service,
            typeLabel: it.label ?? '',
            official: it.official_env_name ?? '',
          })
        }
      } catch {
        get().showToast('분류 서버에 연결하지 못했어요 - 이름과 값만으로 진행합니다')
      }

      const rows: EnvImportRow[] = parsed.map((p) => {
        const hit = byValue.get(p.value)
        return {
          id: crypto.randomUUID(),
          name: p.name,
          value: p.value,
          checked: true, // 비시크릿 줄도 전부 가져온다
          service: hit?.service ?? null,
          typeLabel: hit?.typeLabel || null,
          suggestedName: hit && hit.official && hit.official !== p.name ? hit.official : null,
        }
      })
      set({ envImportOpen: true, envImportRows: rows, envImportProject: '' })
    },

    closeEnvImport: () => set({ envImportOpen: false, envImportRows: [], envImportProject: '' }),

    patchEnvRow: (id, patch) =>
      set((s) => ({
        envImportRows: s.envImportRows.map((r) => (r.id === id ? { ...r, ...patch } : r)),
      })),

    setEnvImportProject: (v) => set({ envImportProject: v }),

    saveEnvImport: async () => {
      const project = get().envImportProject.trim()
      if (!project) {
        get().showToast('컬렉션 이름을 먼저 입력해 주세요')
        return
      }
      const rows = get().envImportRows.filter((r) => r.checked && r.name.trim())
      if (!rows.length) {
        get().showToast('저장할 항목을 선택해 주세요')
        return
      }
      set({ envImportBusy: true })
      let saved = 0
      const savedIds: string[] = []
      for (const r of rows) {
        const name = r.name.trim()
        // 이미 같은 컬렉션에 같은 변수명이 있으면 건너뛴다.
        if (get().vault.some((v) => v.varName === name && (v.project || '') === project)) {
          continue
        }
        const found = findServiceByVarName(name)
        try {
          await vaultApi.add({
            service: found ? SERVICE_TO_ID[found.service] : null,
            kind: found ? found.type.v : null,
            official_name: name,
            value: r.value,
            label: found ? found.type.label : null,
            project,
            memo: null,
            expires_at: jwtExp(r.value),
          })
          saved++
          savedIds.push(r.id)
        } catch (e) {
          if (e instanceof VaultApiError && e.status === 401) {
            get().showToast('금고가 잠겨 저장할 수 없어요 - 잠금을 해제하세요')
            break
          }
          get().showToast(vaultErrorText(e, `${name} 저장 실패 - 잠시 후 다시 시도해 보세요`))
        }
      }
      // 성공분만 목록에서 빼고, 실패분은 남겨 재시도할 수 있게 한다.
      const remaining = get().envImportRows.filter((r) => !savedIds.includes(r.id))
      set({ envImportRows: remaining, envImportBusy: false, envImportOpen: remaining.length > 0 })
      if (saved) {
        await get().loadVault()
        get().showToast(`${saved}개 저장됨 - AES-256-GCM 암호화`)
      }
    },
```

- [ ] **Step 4: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: 출력 없음.
확인된 계약(`src/api/types.ts`): `AnalyzeApiRequest = { text?: string; url?: string }`,
`AnalyzeApiResponse = { items: ClassifiedItem[]; count: number }`,
`ClassifiedItem` 에 `value` · `service: string | null` · `label: string` · `official_env_name: string | null` 이 있다.
위 코드는 이 계약에 맞춰 쓰였다.

- [ ] **Step 5: 기존 테스트 회귀 확인**

Run: `cd frontend && npm test`
Expected: 49 tests passed (기존 그대로)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/store/keylensStore.ts
git commit -m "feat(env-import): 가져오기 상태·액션 추가

.env 를 파싱해 권위 있는 목록을 만들고 /analyze 로 분류만 보강한다. 분류 서버가
죽어 있어도 이름·값만으로 진행한다. 컬렉션이 비면 저장을 막아 등록일 컬렉션으로
새는 것을 원천 차단한다. 1MB/200줄 상한."
```

---

## Task 4: 가져오기 모달 + 드롭 연결

**Files:**
- Create: `frontend/src/components/modals/EnvImportModal.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/screens/InputScreen.tsx:48-64`

**Interfaces:**
- Consumes: `InlineEdit` (Task 2), 스토어 액션 `openEnvImport`/`closeEnvImport`/`patchEnvRow`/`setEnvImportProject`/`saveEnvImport` (Task 3)
- Produces: `export function EnvImportModal(): JSX.Element`

- [ ] **Step 1: 모달 작성**

Create `frontend/src/components/modals/EnvImportModal.tsx`:

```tsx
// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { Modal } from '@/components/ui/Modal'
import { InlineEdit } from '@/components/ui/InlineEdit'
import { mask } from '@/lib/format'
import { useKeylens } from '@/store/keylensStore'

/**
 * `.env` 가져오기 - 파싱된 변수를 표로 보여주고 컬렉션 하나로 일괄 저장한다.
 *
 * 값은 기본적으로 마스킹해 보여준다. .env 는 한 파일에 시크릿이 여러 개라 표를 열어둔
 * 채로 화면을 공유하면 전부 노출되기 때문이다. 더블클릭해 편집에 들어갔을 때만 평문이
 * 보인다.
 */
export function EnvImportModal() {
  const open = useKeylens((s) => s.envImportOpen)
  const rows = useKeylens((s) => s.envImportRows)
  const project = useKeylens((s) => s.envImportProject)
  const busy = useKeylens((s) => s.envImportBusy)
  const close = useKeylens((s) => s.closeEnvImport)
  const patch = useKeylens((s) => s.patchEnvRow)
  const setProject = useKeylens((s) => s.setEnvImportProject)
  const save = useKeylens((s) => s.saveEnvImport)

  const checked = rows.filter((r) => r.checked && r.name.trim()).length
  const canSave = !!project.trim() && checked > 0 && !busy

  return (
    <Modal open={open} onClose={close} title=".env 가져오기" className="w-[720px]">
      <div className="text-[15px] font-bold">.env 가져오기</div>
      <p className="mt-1 text-[12.5px] text-muted">
        {rows.length}개를 찾았어요. 이름이나 값을 <strong className="text-fg-soft">더블클릭</strong>하면
        고칠 수 있어요.
      </p>

      <label className="mt-4 block text-[12px] font-semibold text-muted">
        컬렉션 <span className="text-danger">*</span>
        <input
          value={project}
          onChange={(e) => setProject(e.target.value)}
          list="kl-projects"
          placeholder="예: my-blog"
          className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-[13px] text-fg outline-none focus:border-border-strong"
        />
      </label>

      <div className="mt-3 max-h-[320px] overflow-y-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-[12.5px]">
          <thead className="sticky top-0 bg-panel text-[11px] text-faint-2">
            <tr>
              <th className="w-[34px] p-2" />
              <th className="p-2 text-left font-semibold">변수명</th>
              <th className="p-2 text-left font-semibold">값</th>
              <th className="w-[150px] p-2 text-left font-semibold">종류</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-line align-top">
                <td className="p-2">
                  <input
                    type="checkbox"
                    checked={r.checked}
                    aria-label={`${r.name} 선택`}
                    onChange={(e) => patch(r.id, { checked: e.target.checked })}
                  />
                </td>
                <td className="p-2">
                  <InlineEdit
                    value={r.name}
                    ariaLabel={`${r.name} 변수명`}
                    mono
                    placeholder="변수명을 입력하세요"
                    onCommit={(next) => patch(r.id, { name: next })}
                  />
                  {r.suggestedName && (
                    <button
                      type="button"
                      onClick={() => patch(r.id, { name: r.suggestedName!, suggestedName: null })}
                      className="mt-1 cursor-pointer rounded border border-border bg-none px-[6px] py-px text-[10.5px] text-faint-2 hover:text-fg-soft"
                    >
                      제안: {r.suggestedName} 적용
                    </button>
                  )}
                  {!r.name.trim() && (
                    <div className="mt-1 text-[10.5px] text-danger">이름이 없으면 저장할 수 없어요</div>
                  )}
                </td>
                <td className="p-2">
                  {/* 평문은 편집 중에만 보인다 - .env 는 한 파일에 시크릿이 여러 개다. */}
                  <InlineEdit
                    value={r.value}
                    displayValue={mask(r.value)}
                    ariaLabel={`${r.name} 값`}
                    mono
                    onCommit={(next) => patch(r.id, { value: next })}
                  />
                </td>
                <td className="p-2 text-[11.5px] text-muted">
                  {r.typeLabel ? `${r.service} · ${r.typeLabel}` : '미상'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <span className="text-[11.5px] text-faint-2">
          {!project.trim() ? '컬렉션 이름을 입력해야 저장할 수 있어요' : `${checked}개 선택됨`}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={close}
            className="cursor-pointer rounded-lg border border-border bg-none px-[14px] py-2 text-[12.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
          >
            취소
          </button>
          <button
            type="button"
            disabled={!canSave}
            onClick={save}
            className="cursor-pointer rounded-lg border-none bg-accent px-[14px] py-2 text-[12.5px] font-bold text-[#07231A] hover:brightness-[1.08] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? '저장 중...' : `${checked}개 저장`}
          </button>
        </div>
      </div>
    </Modal>
  )
}
```

- [ ] **Step 2: `mask` 와 `accent` 색 토큰 확인**

Run: `cd frontend && grep -n "export function mask" src/lib/format.ts && grep -rn "bg-accent" src/components | head -2`
Expected: `mask` 가 export 되어 있고 `bg-accent` 를 쓰는 기존 버튼이 있다. 없으면 `EnvModal` 의 기본 버튼 클래스를 그대로 복사해 쓴다.

- [ ] **Step 3: App 에 마운트**

`frontend/src/App.tsx` 의 `<EnvModal />` 바로 아래 줄에 추가:

```tsx
      <EnvImportModal />
```

같은 파일 import 에 추가:

```tsx
import { EnvImportModal } from '@/components/modals/EnvImportModal'
```

- [ ] **Step 4: 드롭 분기 확장**

`frontend/src/components/screens/InputScreen.tsx` 의 `onDrop` 에서 `} else if (f) {` 블록을 아래로 교체한다:

```tsx
    } else if (f) {
      // .env 처럼 확장자가 없거나 text/plain 인 파일은 텍스트로 읽어 가져오기 모달을 연다.
      const rd = new FileReader()
      rd.onload = () => {
        if (typeof rd.result === 'string') s.openEnvImport(rd.result)
        else s.showToast('파일을 읽지 못했어요 - 다른 파일로 시도해 주세요')
      }
      rd.onerror = () => s.showToast('파일을 읽지 못했어요 - 다른 파일로 시도해 주세요')
      rd.readAsText(f)
    } else {
```

`openEnvImport` 를 쓰려면 컴포넌트 상단에서 스토어를 이미 `s` 로 받고 있는지 확인한다(같은 함수 안에서 `s.attachImage`·`s.showToast` 를 쓰고 있으므로 그대로 쓰면 된다).

- [ ] **Step 5: 안내 문구 갱신**

같은 파일 `InputScreen.tsx:134-136` 의 드롭존 문구 두 줄을 아래로 교체한다.

찾을 것:
```tsx
                <div className="mt-3 text-[14px] font-semibold">스크린샷을 여기로 던져보세요</div>
```
그리고 그 아래 줄:
```tsx
                  드래그 앤 드롭 · ⌘V 붙여넣기 · 클릭하면 샘플 첨부
```

바꿀 것:
```tsx
                <div className="mt-3 text-[14px] font-semibold">
                  스크린샷이나 .env 파일을 여기로 던져보세요
                </div>
```
```tsx
                  드래그 앤 드롭 · ⌘V 붙여넣기 · 클릭하면 샘플 첨부 · .env 는 변수 전체를 한 번에
```

- [ ] **Step 6: 타입체크 + 빌드**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 타입 오류 없음, 빌드 성공

- [ ] **Step 7: 수동 확인**

Run: `cd .. && node scripts/dev.mjs`
- 브라우저에서 `http://localhost:5173` 접속 → 잠금 해제
- 아래 내용으로 `test.env` 를 만들어 입력 화면에 끌어다 놓는다:
  ```
  OPENAI_API_KEY=sk-proj-aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ012345
  MY_CUSTOM_NAME=ghp_aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpP1234
  DB_HOST=localhost
  ```
Expected:
- 3줄 모두 표에 뜨고 전부 체크됨
- `MY_CUSTOM_NAME` 이 그대로 보이고, 옆에 "제안: GITHUB_TOKEN 적용" 버튼이 있다
- `DB_HOST` 는 종류가 "미상" 이지만 체크되어 있다
- 컬렉션이 비면 저장 버튼이 비활성
- 변수명을 더블클릭하면 테두리가 진해지고 커서가 깜빡인다

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/modals/EnvImportModal.tsx frontend/src/App.tsx frontend/src/components/screens/InputScreen.tsx
git commit -m "feat(env-import): 가져오기 모달 + .env 드롭 연결

값은 기본 마스킹하고 더블클릭 편집 중에만 평문을 보여준다 - .env 는 한 파일에
시크릿이 여러 개라 표를 열어둔 채 화면을 공유하면 전부 노출되기 때문이다.
컬렉션이 비면 저장 버튼이 비활성이다."
```

---

## Task 5: 결과 카드 변수명 편집 + 저장 시 이름 우선순위

**Files:**
- Modify: `frontend/src/components/input/ResultCard.tsx`
- Modify: `frontend/src/store/keylensStore.ts` (`saveAll`)

**Interfaces:**
- Consumes: `InlineEdit` (Task 2), `AnalysisResult.varName` (Task 3)
- Produces: 없음(최종 소비자)

- [ ] **Step 1: 결과 카드에 변수명 줄 추가**

`frontend/src/components/input/ResultCard.tsx` 의 컬렉션 입력(`placeholder="컬렉션"`) **바로 위**에 추가한다. 파일 상단 import 에 `InlineEdit` 를 넣는다:

```tsx
import { InlineEdit } from '@/components/ui/InlineEdit'
```

컬렉션 입력 앞에 삽입:

```tsx
      <div className="mb-2">
        <div className="mb-1 text-[11px] font-semibold text-faint-2">변수명</div>
        <InlineEdit
          value={r.varName || cur?.var || ''}
          ariaLabel="변수명"
          mono
          placeholder="변수명을 입력하세요"
          onCommit={(next) => patchResult(r.id, { varName: next })}
        />
        {cur?.var && (r.varName || '') && r.varName !== cur.var && (
          <button
            type="button"
            onClick={() => patchResult(r.id, { varName: cur.var })}
            className="mt-1 cursor-pointer rounded border border-border bg-none px-[6px] py-px text-[10.5px] text-faint-2 hover:text-fg-soft"
          >
            제안: {cur.var} 적용
          </button>
        )}
      </div>
```

`cur` 은 이 파일 상단에 이미 있다(`const cur = tmap.find((t) => t.v === r.typeKey) || null`). `cur.var` 필드명이 다르면 `TYPE_MAP` 정의를 보고 맞춘다.

- [ ] **Step 2: 저장 시 사용자 지정 이름 우선**

`frontend/src/store/keylensStore.ts` 의 `saveAll` 안에서 아래 줄을 찾는다:

```ts
        const t = TYPE_MAP[r.service].find((tt) => tt.v === r.typeKey)!
        if (findDup(r, t.var)) {
```

이것으로 교체한다:

```ts
        const t = TYPE_MAP[r.service].find((tt) => tt.v === r.typeKey)!
        // 사용자가 변수명을 직접 정했으면 그것이 이긴다(.env 가져오기·인라인 편집).
        // 안 건드렸으면 지금까지처럼 종류에서 공식 이름을 도출한다.
        const varName = (r.varName || '').trim() || t.var
        if (findDup(r, varName)) {
```

같은 블록의 `official_name: t.var,` 을 아래로 바꾼다:

```ts
            official_name: varName,
```

- [ ] **Step 3: 타입체크 + 기존 테스트**

Run: `cd frontend && npx tsc --noEmit && npm test`
Expected: 타입 오류 없음, 49 tests passed

- [ ] **Step 4: 수동 확인**

`node scripts/dev.mjs` 로 띄우고 텍스트 칸에 `ghp_aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpP1234` 를 붙여넣어 분석한다.
Expected:
- 결과 카드에 "변수명 `GITHUB_TOKEN`" 이 보인다
- 더블클릭해 `MY_NAME` 으로 고치고 컬렉션을 넣어 저장하면, 보관함에 `MY_NAME` 으로 들어간다
- 변수명을 안 건드리고 저장하면 지금까지처럼 `GITHUB_TOKEN` 으로 들어간다(회귀 없음)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/input/ResultCard.tsx frontend/src/store/keylensStore.ts
git commit -m "feat(env-import): 결과 카드에서 변수명 편집 + 저장 시 사용자 이름 우선

지금까지 official_name 은 종류에서 강제 도출됐다. 사용자가 정한 이름이 있으면
그것이 이기고, 안 건드리면 기존 동작 그대로다."
```

---

## Task 6: 보관함 값 더블클릭 → 회전

**Files:**
- Modify: `frontend/src/components/vault/VaultRow.tsx`

**Interfaces:**
- Consumes: 스토어 `openRotate(it: VaultItem)` (기존)
- Produces: 없음

- [ ] **Step 1: 값 표시에 더블클릭 핸들러 추가**

`frontend/src/components/vault/VaultRow.tsx:58-65` 의 값 블록 전체를 교체한다.

찾을 것:
```tsx
        {/* 값(마스킹/공개 토글) */}
        <div
          onClick={() => reveal(it.id)}
          title={locked ? '잠금 해제 후 볼 수 있어요' : canSee ? '클릭하여 숨기기' : '클릭하여 4초간 표시'}
          className="cursor-pointer overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[12.5px]"
          style={{ color: canSee ? '#A7E8C9' : '#727C89' }}
        >
          {canSee ? it.full : it.masked}
        </div>
```

바꿀 것:
```tsx
        {/* 값(마스킹/공개 토글). 더블클릭은 회전 모달로 가는 지름길 - 값 교체는 재암호화와
            이력 기록이 따라야 해서 표 안에서 직접 고치지 않는다. */}
        <div
          onClick={() => reveal(it.id)}
          onDoubleClick={() => !locked && openRotate(it)}
          title={
            locked
              ? '잠금 해제 후 볼 수 있어요'
              : canSee
                ? '클릭하여 숨기기 · 더블클릭하면 값 교체'
                : '클릭하여 4초간 표시 · 더블클릭하면 값 교체'
          }
          className="cursor-pointer overflow-hidden text-ellipsis whitespace-nowrap rounded font-mono text-[12.5px] hover:bg-surface"
          style={{ color: canSee ? '#A7E8C9' : '#727C89' }}
        >
          {canSee ? it.full : it.masked}
        </div>
```

`openRotate` 는 이 파일 27번째 줄에 이미 `const openRotate = useKeylens((s) => s.openRotate)` 로 있다.
잠긴 상태에서는 회전할 수 없으므로 `!locked` 로 막는다.

- [ ] **Step 2: 타입체크 + 빌드**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: 오류 없음

- [ ] **Step 3: 수동 확인**

보관함에서 값 영역을 더블클릭 → 회전 모달이 뜬다. 새 값을 넣고 확정하면 이력에 "키 회전" 이 남는다.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/vault/VaultRow.tsx
git commit -m "feat(vault): 값 더블클릭으로 회전 모달 열기

값 교체는 재암호화+이력 기록이 필요해 기존 회전 경로를 그대로 쓴다.
더블클릭은 회전 버튼을 찾아 누르는 수고를 줄이는 지름길이다."
```

---

## Task 7: 문서 갱신

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: README 주요 기능에 한 줄 추가**

`README.md` 의 "런타임 키 주입 SDK" 항목 **바로 위**에 추가:

```markdown
- **`.env` 가져오기**: 이미 쓰던 `.env` 파일을 앱에 끌어다 놓으면 변수 전체를 한 화면에서 확인·편집하고 컬렉션 하나로 일괄 저장합니다. **원본 변수명을 그대로 지킵니다** - 소비 레포 코드가 이미 그 이름을 읽고 있으니까요. 이름·값은 더블클릭으로 그 자리에서 고칠 수 있습니다
```

- [ ] **Step 2: CHANGELOG Unreleased 에 추가**

`CHANGELOG.md` 의 `## [Unreleased]` 아래 `### Added (기능)` 에 추가:

```markdown
- **`.env` 가져오기**: `.env` 파일을 드롭하면 변수 전체를 표로 보여주고 컬렉션 하나로 일괄 저장합니다.
  원본 변수명을 그대로 유지하며(지식베이스 공식 이름은 "제안"으로만 노출), 분류가 안 되는 줄
  (`DB_HOST` 등)도 함께 가져옵니다. 이름·값은 더블클릭으로 편집할 수 있고, 보관함에서 값을
  더블클릭하면 기존 회전 모달이 열립니다. 설계: [`docs/superpowers/specs/2026-08-30-env-import-design.md`](docs/superpowers/specs/2026-08-30-env-import-design.md)
```

- [ ] **Step 3: 최종 검증**

Run: `cd frontend && npm test && npx tsc --noEmit && npm run build`
Expected: 전부 통과

Run: `cd .. && backend/.venv/Scripts/python.exe -m reuse lint-file frontend/src/lib/envParse.ts frontend/src/components/ui/InlineEdit.tsx frontend/src/components/modals/EnvImportModal.tsx`
Expected: SPDX 누락 없음
(참고: Windows 에서 `reuse lint` 전체 실행은 한글 파일에 대해 거짓 실패를 낸다 - 판단은 CI 로 한다)

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md
git commit -m "docs(env-import): README 주요 기능 + CHANGELOG 항목 추가"
```
