// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
/**
 * RUNTIME-1 SDK 접근 관리 슬라이스 — 승인 대기, 허용 디렉토리, 네이티브 폴더 찾기.
 *
 * `keylensStore.ts` 하나가 1,700줄까지 커지면서 "이 액션이 건드려야 할 상태"를 한눈에 볼 수
 * 없게 됐고, 실제로 그 때문에 버그가 났다(승인 후 `allSdkDirs` 갱신 누락, 커밋 1388052).
 * 이 구역은 상태 7개와 액션 12개가 서로만 참조하는 명확한 덩어리라 가장 먼저 떼어낸다.
 *
 * 주의: 화면·문서에서는 '컬렉션'이지만 백엔드 API·DB 컬럼명은 계속 `project` 다
 * (keylens-env 가 다른 레포에 버전 고정으로 설치되므로 와이어 포맷은 바꾸지 않는다).
 * 그래서 아래 식별자들도 `sdkProject*` 이름을 유지한다.
 */
import { desktopApi, sdkApi, VaultApiError } from '@/api/client'
import type { PendingRequest, SdkDir, SdkDirEntry, SdkProjectSummary } from '@/types'

/** 이 슬라이스가 소유하는 상태와 액션. */
export interface SdkAccessState {
  /** RUNTIME-1 승인 대기 목록(값 없음 - 컬렉션·경로 문자열만). */
  pendingRequests: PendingRequest[]
  /** 금고에 컬렉션이 지정된 항목이 있는 컬렉션 목록. */
  sdkProjects: SdkProjectSummary[]
  /** 설정 화면에서 선택된 컬렉션(없으면 null). */
  selectedSdkProject: string | null
  /** 선택된 컬렉션의 허용 디렉토리 목록. */
  sdkDirs: SdkDir[]
  /** 디렉토리 추가 입력 필드 값. */
  newDirPath: string
  /**
   * 모든 컬렉션의 허용 디렉토리(승인 대기 화면의 "이미 허용한 디렉토리" 섹션용).
   * `sdkDirs` 는 선택된 컬렉션 하나만 담으므로 별도로 둔다.
   */
  allSdkDirs: SdkDirEntry[]
  /**
   * 데스크톱 앱에서 네이티브 폴더 선택창을 쓸 수 있는지. 브라우저에서는 false 이며,
   * 그때는 "찾아보기" 버튼을 아예 그리지 않는다 - 눌렀을 때 실패하는 것보다 낫다.
   */
  canPickDirectory: boolean

  /** 승인 대기 목록을 백엔드에서 다시 불러온다. */
  loadPending: () => Promise<void>
  /** 대기 요청 허용(= 그 디렉토리를 컬렉션에 등록). */
  approvePending: (id: number) => Promise<void>
  /** 대기 요청 거부. */
  denyPending: (id: number) => Promise<void>
  /** SDK 컬렉션 목록을 백엔드에서 다시 불러온다. */
  loadSdkProjects: () => Promise<void>
  /** 컬렉션을 선택하고 그 컬렉션의 허용 디렉토리 목록을 불러온다. */
  selectSdkProject: (project: string) => Promise<void>
  /** 새 디렉토리 입력 필드 값 설정. */
  setNewDirPath: (v: string) => void
  /** 선택된 컬렉션에 디렉토리를 사전 등록(source=manual, 승인 팝업 없이 바로 통과). */
  addSdkDir: () => Promise<void>
  /** 선택된 컬렉션에서 디렉토리 등록 해제. */
  removeSdkDir: (dirId: number) => Promise<void>
  /** 모든 컬렉션의 허용 디렉토리를 불러온다. */
  loadAllSdkDirs: () => Promise<void>
  /** 컬렉션을 지정해 허용을 철회한다(선택된 컬렉션과 무관하게 동작). */
  revokeSdkDir: (project: string, dirId: number) => Promise<void>
  /** 네이티브 폴더 선택창을 열어 고른 경로를 입력 필드에 넣는다(데스크톱 전용). */
  pickSdkDir: () => Promise<void>
  /** 데스크톱 전용 기능 유무를 확인해 저장한다. */
  loadDesktopCapabilities: () => Promise<void>
}

/**
 * 이 슬라이스가 **바깥 상태에서** 필요로 하는 것. 전체 스토어 타입을 가져오면 순환 참조가
 * 되므로, 쓰는 것만 구조적으로 선언한다.
 */
export interface SdkAccessDeps {
  showToast: (msg: string) => void
  /** 401 을 만나면 잠긴 사실을 여기에 반영한다(이 슬라이스는 읽지 않고 쓰기만 한다). */
  locked: boolean
}

type Slice = SdkAccessState & SdkAccessDeps
type Set = (partial: Partial<Slice>) => void
type Get = () => Slice

/** 실패 메시지를 만든다. 스토어 본체의 `vaultErrorText` 와 같은 규칙. */
type ErrorText = (e: unknown, fallback: string) => string

export const sdkAccessInitialState: Pick<
  SdkAccessState,
  | 'pendingRequests'
  | 'sdkProjects'
  | 'selectedSdkProject'
  | 'sdkDirs'
  | 'newDirPath'
  | 'allSdkDirs'
  | 'canPickDirectory'
> = {
  pendingRequests: [],
  sdkProjects: [],
  selectedSdkProject: null,
  sdkDirs: [],
  newDirPath: '',
  allSdkDirs: [],
  canPickDirectory: false,
}

export function createSdkAccessSlice(set: Set, get: Get, errorText: ErrorText): SdkAccessState {
  return {
    ...sdkAccessInitialState,

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
        // 허용은 곧 디렉토리 등록이다 - 같은 화면의 "이미 허용한 디렉토리"가 그 자리에서
        // 늘어나야 한다. 대기 목록만 새로 불러오면 방금 허용한 항목이 어디에도 안 보인다.
        await Promise.all([get().loadPending(), get().loadAllSdkDirs()])
        get().showToast('요청을 허용했어요 — 이후 자동으로 값을 받아갑니다')
      } catch (e) {
        // 허용은 권한 부여라 백엔드가 잠금 해제를 요구한다(401) — 잠긴 사실을 UI에 반영한다.
        if (e instanceof VaultApiError && e.status === 401) set({ locked: true })
        get().showToast(errorText(e, '허용 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },

    denyPending: async (id) => {
      try {
        await sdkApi.deny(id)
        await get().loadPending()
        get().showToast('요청을 거부했어요')
      } catch (e) {
        get().showToast(errorText(e, '거부 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },

    loadSdkProjects: async () => {
      try {
        const rows = await sdkApi.projects()
        set({ sdkProjects: rows.map((p) => ({ project: p.project, keyCount: p.key_count })) })
      } catch {
        /* 목록 로딩 실패는 조용히 무시 */
      }
    },

    selectSdkProject: async (project) => {
      set({ selectedSdkProject: project, sdkDirs: [] })
      try {
        const rows = await sdkApi.dirs(project)
        set({
          sdkDirs: rows.map((d) => ({
            id: d.id,
            path: d.path,
            source: d.source,
            createdAt: d.created_at,
          })),
        })
      } catch (e) {
        get().showToast(errorText(e, '디렉토리 목록을 불러오지 못했어요'))
      }
    },

    setNewDirPath: (v) => set({ newDirPath: v }),

    addSdkDir: async () => {
      const project = get().selectedSdkProject
      const path = get().newDirPath.trim()
      if (!project) return
      if (!path) {
        get().showToast('등록할 디렉토리 경로를 입력해 주세요')
        return
      }
      try {
        await sdkApi.addDir(project, path)
        set({ newDirPath: '' })
        await get().selectSdkProject(project)
        get().showToast('디렉토리를 등록했어요 — 이후 자동으로 값을 받아갑니다')
      } catch (e) {
        // 등록도 권한 부여다(위 approvePending 과 같은 이유로 401 가능).
        if (e instanceof VaultApiError && e.status === 401) set({ locked: true })
        get().showToast(errorText(e, '디렉토리 등록 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },

    removeSdkDir: async (dirId) => {
      const project = get().selectedSdkProject
      if (!project) return
      await get().revokeSdkDir(project, dirId)
      await get().selectSdkProject(project)
    },

    loadAllSdkDirs: async () => {
      try {
        const rows = await sdkApi.allDirs()
        set({
          allSdkDirs: rows.map((d) => ({
            id: d.id,
            project: d.project,
            path: d.path,
            source: d.source,
            createdAt: d.created_at,
          })),
        })
      } catch {
        /* 목록 로딩 실패는 조용히 무시 - 접힌 섹션이라 사용자가 보고 있지 않을 수 있다. */
      }
    },

    revokeSdkDir: async (project, dirId) => {
      try {
        await sdkApi.removeDir(project, dirId)
        // 낙관적 갱신 대신 다시 불러온다 - 두 화면이 같은 목록을 보므로 어긋나면 안 된다.
        await get().loadAllSdkDirs()
        get().showToast('허용을 철회했어요 - 다음 요청부터 다시 승인을 받습니다')
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) set({ locked: true })
        get().showToast(errorText(e, '철회 실패 - 잠시 후 다시 시도해 보세요'))
      }
    },

    loadDesktopCapabilities: async () => {
      try {
        const caps = await desktopApi.capabilities()
        set({ canPickDirectory: caps.directory_picker })
      } catch {
        // 못 물어봤으면 없는 것으로 둔다 - 있다고 가정했다가 눌렀을 때 실패하는 것보다 낫다.
        set({ canPickDirectory: false })
      }
    },

    pickSdkDir: async () => {
      try {
        const { path } = await desktopApi.pickDirectory()
        // 취소는 정상 흐름이다 - 토스트를 띄우지 않는다.
        if (path) set({ newDirPath: path })
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) set({ locked: true })
        get().showToast(errorText(e, '폴더 찾기를 열지 못했어요 - 경로를 직접 입력해 주세요'))
      }
    },
  }
}
