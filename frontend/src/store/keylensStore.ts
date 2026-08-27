// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
//
// KeyLens 앱 상태 스토어.
// 프로토타입 KeyLens.dc.html의 DCLogic 클래스(state + 메서드)를 Zustand로 이식했다.
// 목업 로직(seed 데이터, 가짜 분석·저장)은 그대로 유지하며,
// 실제 백엔드(SPEC 5장: OCR·분류·암호화·SQLite)로 교체할 지점은 seed.ts / services.ts로 분리해 둔다.
import { create } from 'zustand'
import {
  analyzeApi,
  analyzeImageApi,
  ApiError,
  explainImageApi,
  explainStatusApi,
  fetchKnowledge,
  sdkApi,
  vaultApi,
  VaultApiError,
} from '@/api/client'
import type { ExplainBox } from '@/api/types'
import { metaToVaultItem, SERVICE_TO_ID, toAnalysisResults } from '@/api/map'
import { applyKnowledge, findServiceByVarName, TYPE_MAP } from '@/data/services'
import { freshResults } from '@/data/seed'
import { splitKeyValue } from '@/lib/autocomplete'
import { envText, jwtExp, passwordPolicyError, projectKey, today } from '@/lib/format'
import { requestEmailExport, SyncRelayError } from '@/lib/syncRelay'
import type {
  AnalysisResult,
  DeleteTarget,
  DupTarget,
  InputMode,
  ManualRow,
  PendingRequest,
  Screen,
  SdkDir,
  SdkProjectSummary,
  UnknownItem,
  VaultItem,
  View,
} from '@/types'

/**
 * VaultApiError면 실제 사유(detail — 네트워크 단절일 때도 vreq가 이미 적절한 문구를 담아 던진다)를
 * 그대로 보여주고, VaultApiError가 아닌 알 수 없는 오류일 때만 fallback을 쓴다.
 * "서버가 응답은 했는데 연결을 확인하라"는 오해를 만들지 않기 위함.
 * 사용자에게는 항상 이해하기 쉬운 문구만 보여주되, 실제 원인(상태 코드·원본 오류)은
 * 개발자 콘솔에 남겨 디버깅이 가능하게 한다.
 */
function vaultErrorText(e: unknown, fallback: string): string {
  if (e instanceof VaultApiError) {
    console.error(`[KeyLens] 금고 요청 실패 (HTTP ${e.status}):`, e.message)
    return e.message
  }
  console.error('[KeyLens] 예상치 못한 오류:', e)
  return fallback
}

/**
 * 직접 입력 탭 — 방금 수정한 행이 배열의 마지막 행이고 이름·값이 둘 다 채워졌으면
 * 빈 행을 하나 더 붙인다("하나 채우면 자동으로 다음 행 생김"). 그 외엔 그대로 반환.
 */
function ensureTrailingEmptyRow(rows: ManualRow[], editedId: string): ManualRow[] {
  const last = rows[rows.length - 1]
  if (last.id !== editedId || !last.name.trim() || !last.value.trim()) return rows
  return [...rows, { id: crypto.randomUUID(), name: '', value: '' }]
}

/** 분석 시뮬레이션 시간(초). 실제 앱에선 백엔드 응답 시간으로 대체. */
const ANALYZE_SECONDS = 1.4
/** 복사한 값이 클립보드에서 자동 삭제되기까지의 시간(ms). */
const CLIP_CLEAR_MS = 30_000

// ── 비반응(non-reactive) 타이머 핸들 ──
let timers: ReturnType<typeof setTimeout>[] = []
let toastT: ReturnType<typeof setTimeout> | null = null
let clipClearT: ReturnType<typeof setTimeout> | null = null
const revealTimers: Record<string, ReturnType<typeof setTimeout>> = {}
// 메타데이터(프로젝트·메모·만료) 편집을 디바운스해 백엔드에 저장한다(키 입력마다 요청 방지).
const metaSaveT: Record<string, ReturnType<typeof setTimeout>> = {}

interface KeylensState {
  // 화면
  screen: Screen
  view: View

  // 설정(최초 실행)
  pw: string
  pw2: string
  setupErr: string

  // 잠금 / 인증
  lockPw: string
  lockErr: string
  lockShakeN: number
  unlocking: boolean
  locked: boolean

  // 입력
  dragOver: boolean
  urlVal: string
  textVal: string
  memoVal: string
  projVal: string
  attachedImage: string | null
  attachedName: string

  /** 화면 설명 기능(1단계) — Ollama 가용 여부(부팅 시 1회 확인). */
  explainAvailable: boolean
  explainOpen: boolean
  explainLoading: boolean
  explainBoxes: ExplainBox[]

  // 직접 입력 탭 — 자동 분류 없이 이름=값을 바로 선언(RUNTIME-1과 무관, UI 전용)
  inputMode: InputMode
  manualRows: ManualRow[]

  // 분석
  analyzing: boolean
  /** 브라우저 OCR 진행률(0~1). 스크린샷 인식 중일 때만 채워지고, 아니면 null. */
  ocrProgress: number | null
  analyzed: boolean
  results: AnalysisResult[]
  /** Stage1에서 값만으로 판별 불가한 항목(맥락 분류 Stage2 대상). */
  unknowns: UnknownItem[]
  /** 백엔드 미연결 등으로 목업 폴백했을 때의 사유(없으면 null). */
  apiError: string | null
  sourceLabel: string
  analyzedImage: string | null

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

  // 다이얼로그 / 토스트
  deleteTarget: DeleteTarget
  dupTarget: DupTarget | null
  /** 값 교체(회전) 대상 항목. 모달이 열려 있으면 non-null. */
  rotateTarget: VaultItem | null
  envOpen: boolean
  /** 금고 가져오기(SYNC-0) 모달 열림 여부. */
  syncOpen: boolean
  /** 이메일로 내보내기(SYNC-2 재설계) 모달 열림 여부. */
  emailSyncOpen: boolean
  /** 금고 완전 초기화 확인 모달 상태(VAULT-RESET) — 교육·공용 PC용, 비밀번호 재확인 필수. */
  resetVaultOpen: boolean
  resetVaultPw: string
  resetVaultErr: string
  resettingVault: boolean
  /** `/knowledge` 로드 완료 여부 — 서비스맵 갱신 시 리렌더 트리거용. */
  knowledgeReady: boolean
  /** RUNTIME-1 승인 대기 목록(값 없음 — 프로젝트·경로 문자열만). */
  pendingRequests: PendingRequest[]
  // RUNTIME-1 — 프로젝트 접근 설정 화면
  /** 금고에 프로젝트가 지정된 항목이 있는 프로젝트 목록. */
  sdkProjects: SdkProjectSummary[]
  /** 설정 화면에서 선택된 프로젝트(없으면 null). */
  selectedSdkProject: string | null
  /** 선택된 프로젝트의 허용 디렉토리 목록. */
  sdkDirs: SdkDir[]
  /** 디렉토리 추가 입력 필드 값. */
  newDirPath: string
  toast: string | null

  // ── 액션 ──
  showToast: (msg: string) => void
  cleanup: () => void
  /** 앱 시작 시 백엔드 금고 상태로 화면(설정/잠금/앱)을 결정. */
  boot: () => void
  /** `/knowledge`로 서비스·종류맵을 동적 구성(실패 시 기본 5종 유지). */
  loadKnowledge: () => Promise<void>
  /** 백엔드에서 금고 항목 메타데이터를 다시 불러온다. */
  loadVault: () => void
  /** 항목 값을 복호화해 클립보드에 복사(잠금 시 인증 유도). prefix 지정 시 `prefix+값`(.env 한 줄). */
  copyValue: (id: string, label: string, prefix?: string) => void
  /** 항목의 감사 이력(등록·열람·복사·내보내기)을 불러와 해당 항목에 채운다. */
  loadHistory: (id: string) => void

  goInput: () => void
  goVault: () => void
  /** 승인 대기 화면으로 전환하고 목록을 새로 불러온다(데스크톱 알림이 evaluate_js로 호출하는 경로). */
  goPending: () => void
  /** 승인 대기 목록을 백엔드에서 다시 불러온다(값 없음 — 잠금 상태에서도 동작). */
  loadPending: () => Promise<void>
  /** 승인 대기 요청을 허용 — 이후 해당 디렉토리는 자동 통과. */
  approvePending: (id: number) => Promise<void>
  /** 승인 대기 요청을 거부. */
  denyPending: (id: number) => Promise<void>
  /** 프로젝트 접근 설정 화면으로 전환하고 프로젝트 목록을 새로 불러온다. */
  goProjectAccess: () => void
  /** SDK 프로젝트 목록을 백엔드에서 다시 불러온다. */
  loadSdkProjects: () => Promise<void>
  /** 프로젝트를 선택하고 그 프로젝트의 허용 디렉토리 목록을 불러온다. */
  selectSdkProject: (project: string) => void
  /** 새 디렉토리 입력 필드 값 설정. */
  setNewDirPath: (v: string) => void
  /** 선택된 프로젝트에 디렉토리를 사전 등록(source=manual, 승인 팝업 없이 바로 통과). */
  addSdkDir: () => void
  /** 디렉토리 등록 해제. */
  removeSdkDir: (dirId: number) => void

  setPw: (v: string) => void
  setPw2: (v: string) => void
  createVault: () => void

  setLockPw: (v: string) => void
  submitUnlock: () => void
  lockNow: () => void
  gotoLockScreen: () => void

  setUrl: (v: string) => void
  setText: (v: string) => void
  setMemo: (v: string) => void
  setProj: (v: string) => void
  setDragOver: (v: boolean) => void
  attachImage: (dataUrl: string, name: string) => void
  attachSample: () => void
  removeImage: () => void
  handlePasteImage: (dataUrl: string) => void
  startAnalyze: () => void
  resetResults: () => void

  // 직접 입력 탭
  setInputMode: (m: InputMode) => void
  setManualField: (id: string, field: 'name' | 'value', v: string) => void
  /** 해당 행의 field 칸에 "NAME=VALUE" 형태가 있으면 이름/값 두 칸으로 분리(Enter 시 호출). */
  splitManualField: (id: string, field: 'name' | 'value') => void
  addManualRow: () => void
  removeManualRow: (id: string) => void
  saveManualRows: () => void

  patchResult: (id: string, patch: Partial<AnalysisResult>) => void
  pickOption: (id: string, k: string) => void
  setType: (id: string, v: string) => void
  save: (id: string, force?: boolean) => void
  confirmDup: () => void
  cancelDup: () => void
  saveAll: () => void

  setSearch: (v: string) => void
  setProjFilter: (v: string) => void
  /** 드롭다운에서 프로젝트 선택 — 그 섹션을 강제로 펼친다(스크롤은 VaultScreen이 처리). */
  expandProject: (name: string) => void
  toggleProjectSection: (name: string, currentlyOpen: boolean) => void
  toggleServiceTag: (name: string) => void
  clearServiceTagFilter: () => void
  reveal: (id: string) => void
  copy: (text: string, label: string) => void
  setVaultField: (id: string, key: keyof VaultItem, v: unknown) => void
  /** 값 교체 모달 열기/닫기/확정(새 값으로 재암호화). */
  openRotate: (it: VaultItem) => void
  cancelRotate: () => void
  confirmRotate: (newValue: string) => void
  setDeleteTarget: (it: VaultItem) => void
  cancelDelete: () => void
  confirmDelete: () => void
  toggleExpanded: (id: string) => void
  /** 키 유효성 검증(TRUST-1) — 서비스로 1회 호출해 active/invalid/unknown 표시. */
  verifyEntry: (id: string) => void

  openEnv: () => void
  closeEnv: () => void
  envCopyAll: () => void
  envDownload: () => void
  /** 한 프로젝트 섹션 안의 특정 서비스만 .env로 복사(project+service 둘 다 일치하는 항목만). */
  envCopyGroup: (project: string, service: string) => void
  /** 한 프로젝트의 모든 서비스를 합쳐 .env로 복사. */
  envCopyProject: (project: string) => void
  /** .env 모달 미리보기용 — 선택 항목을 복호화해 반환(모달 렌더링 전용, 클립보드/다운로드와 별개 호출). */
  loadEnvPreview: () => Promise<VaultItem[]>

  /** 암호화 금고 내보내기/가져오기(SYNC-0). */
  exportVault: () => void
  openSync: () => void
  closeSync: () => void
  importVault: (file: File, password: string, mode: 'replace' | 'merge') => Promise<boolean>
  /** 이메일 릴레이로 내보내기(SYNC-2 재설계, 계정/DB 없음). */
  openEmailSync: () => void
  closeEmailSync: () => void
  emailExport: (destEmail: string) => Promise<boolean>

  /** 화면 설명(1단계, 검색·캐시 없음). */
  checkExplainAvailable: () => Promise<void>
  openExplain: () => Promise<void>
  closeExplain: () => void

  /** 금고 완전 초기화(VAULT-RESET). */
  openResetVault: () => void
  closeResetVault: () => void
  setResetVaultPw: (v: string) => void
  confirmResetVault: () => Promise<void>

  resetProto: () => void
}

export const useKeylens = create<KeylensState>((set, get) => {
  /** 관리되는 setTimeout — cleanup()으로 일괄 정리. */
  const timer = (fn: () => void, ms: number) => {
    const id = setTimeout(fn, ms)
    timers.push(id)
    return id
  }

  // 값(full)은 로컬에 두지 않으므로 중복은 변수명+프로젝트(메타데이터)로만 판단한다.
  // project 미지정 저장은 백엔드가 오늘(UTC) 날짜를 기본값으로 배정하므로, 아직 저장 전인 pending
  // 결과(r.project === '')는 각 기존 항목이 실제로 배정받은 addedAt 과 비교해 매칭한다("오늘 날짜"를
  // 프론트에서 별도로 재계산하지 않는다 — 로컬 today()는 UTC 자정 경계에서 백엔드와 어긋날 수 있다).
  const findDup = (r: AnalysisResult, varName: string): VaultItem | undefined => {
    const rp = (r.project || '').trim()
    return get().vault.find(
      (v) =>
        v.varName === varName &&
        (rp ? (v.project || '') === rp : !v.project || v.project === v.addedAt),
    )
  }

  // .env 내보내기용으로 각 항목의 값을 복호화해 채운다(잠금/실패 항목은 제외).
  const withValues = async (items: VaultItem[]): Promise<VaultItem[]> => {
    const out: VaultItem[] = []
    for (const it of items) {
      try {
        const { value } = await vaultApi.value(Number(it.id), 'export')
        out.push({ ...it, full: value })
      } catch {
        /* 잠금/네트워크 실패 항목은 건너뜀 */
      }
    }
    return out
  }

  const envItems = (): VaultItem[] => {
    const s = get()
    return s.vault.filter((v) => !s.projFilter || (v.project || '') === s.projFilter)
  }

  return {
    screen: 'setup',
    view: 'input',
    pw: '',
    pw2: '',
    setupErr: '',
    lockPw: '',
    lockErr: '',
    lockShakeN: 0,
    unlocking: false,
    locked: false,
    dragOver: false,
    urlVal: '',
    textVal: '',
    memoVal: '',
    projVal: '',
    attachedImage: null,
    attachedName: '',
    explainAvailable: false,
    explainOpen: false,
    explainLoading: false,
    explainBoxes: [],
    inputMode: 'auto',
    manualRows: [{ id: crypto.randomUUID(), name: '', value: '' }],
    analyzing: false,
    ocrProgress: null,
    analyzed: false,
    results: [],
    unknowns: [],
    apiError: null,
    sourceLabel: '',
    analyzedImage: null,
    vault: [],
    search: '',
    projFilter: '',
    projectOpenOverrides: {},
    serviceTagFilter: new Set(),
    revealed: {},
    expandedId: null,
    deleteTarget: null,
    dupTarget: null,
    rotateTarget: null,
    envOpen: false,
    syncOpen: false,
    emailSyncOpen: false,
    resetVaultOpen: false,
    resetVaultPw: '',
    resetVaultErr: '',
    resettingVault: false,
    knowledgeReady: false,
    pendingRequests: [],
    sdkProjects: [],
    selectedSdkProject: null,
    sdkDirs: [],
    newDirPath: '',
    toast: null,

    showToast: (msg) => {
      if (toastT) clearTimeout(toastT)
      set({ toast: msg })
      toastT = setTimeout(() => set({ toast: null }), 2800)
    },
    cleanup: () => {
      timers.forEach(clearTimeout)
      timers = []
      if (toastT) clearTimeout(toastT)
      if (clipClearT) clearTimeout(clipClearT)
      Object.values(revealTimers).forEach(clearTimeout)
    },

    goInput: () => {
      // 분석 결과·판독불가 화면에 갇힌 상태로 홈 탭을 눌러도 항상 빠져나올 수 있어야 한다.
      if (get().analyzed) get().resetResults()
      set({ view: 'input' })
    },
    goVault: () => set({ view: 'vault' }),
    goPending: () => {
      set({ view: 'pending' })
      get().loadPending()
    },
    goProjectAccess: () => {
      set({ view: 'projectAccess' })
      get().loadSdkProjects()
    },

    // ── 부팅 / 금고 로딩 ──
    loadKnowledge: async () => {
      try {
        applyKnowledge(await fetchKnowledge())
        set({ knowledgeReady: true }) // 서비스맵 갱신 → 구독 컴포넌트 리렌더
      } catch {
        /* 백엔드 미연결 — 기본 5종 맵 유지 */
      }
    },
    boot: async () => {
      await get().loadKnowledge() // 지식베이스로 서비스·종류맵 구성(화면 렌더 전)
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
        get().checkExplainAvailable()
      } catch (e) {
        // 백엔드 미연결 — 금고 기능은 백엔드가 필요하다. 설정 화면 + 안내.
        console.error('[KeyLens] 부팅 시 금고 상태 조회 실패:', e)
        set({ screen: 'setup' })
        get().showToast('금고 기능을 쓰려면 KeyLens 서버가 켜져 있어야 해요 — 잠시 후 다시 시도해 보세요')
      }
    },
    loadVault: async () => {
      try {
        const metas = await vaultApi.list()
        set({ vault: metas.map(metaToVaultItem) })
      } catch {
        /* 목록 로딩 실패는 조용히 무시(잠금/네트워크) */
      }
    },
    copyValue: async (id, label, prefix) => {
      try {
        const { value } = await vaultApi.value(Number(id), 'copy')
        get().copy((prefix ?? '') + value, label)
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) {
          set({ locked: true })
          get().showToast('잠금 상태입니다 — 먼저 잠금을 해제하세요')
        } else {
          get().showToast('값을 불러오지 못했어요')
        }
      }
    },
    loadHistory: async (id) => {
      try {
        const hist = await vaultApi.history(Number(id))
        set((s) => ({ vault: s.vault.map((it) => (it.id === id ? { ...it, history: hist } : it)) }))
      } catch {
        /* 잠금/네트워크 실패는 무시(이력만 비어 보임) */
      }
    },
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
        get().showToast(vaultErrorText(e, '디렉토리 목록을 불러오지 못했어요'))
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
        get().showToast(vaultErrorText(e, '디렉토리 등록 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },
    removeSdkDir: async (dirId) => {
      const project = get().selectedSdkProject
      if (!project) return
      try {
        await sdkApi.removeDir(project, dirId)
        await get().selectSdkProject(project)
        get().showToast('디렉토리 등록을 해제했어요')
      } catch (e) {
        get().showToast(vaultErrorText(e, '해제 실패 — 잠시 후 다시 시도해 보세요'))
      }
    },

    // ── 설정(최초 실행) ──
    setPw: (v) => set({ pw: v, setupErr: '' }),
    setPw2: (v) => set({ pw2: v, setupErr: '' }),
    createVault: async () => {
      const { pw, pw2 } = get()
      const policyErr = passwordPolicyError(pw)
      if (policyErr) {
        set({ setupErr: policyErr })
        return
      }
      if (pw !== pw2) {
        set({ setupErr: '비밀번호가 일치하지 않아요.' })
        return
      }
      set({ unlocking: true, setupErr: '' })
      try {
        await vaultApi.init(pw)
        set({ screen: 'app', view: 'input', unlocking: false, pw: '', pw2: '', locked: false })
        get().loadVault()
        get().showToast('금고 생성 완료 — 값은 AES-256-GCM으로 암호화되어 이 기기에만 저장됩니다')
      } catch (e) {
        const conflict = e instanceof VaultApiError && e.status === 409
        set({
          unlocking: false,
          setupErr: conflict
            ? '이미 금고가 있어요 — 잠금 해제로 진행하세요.'
            : vaultErrorText(e, '금고 생성 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요.'),
        })
        if (conflict) set({ screen: 'lock', locked: true })
      }
    },

    // ── 잠금 / 해제 ──
    setLockPw: (v) => set({ lockPw: v, lockErr: '' }),
    submitUnlock: async () => {
      if (get().unlocking) return
      if (!get().lockPw) {
        set({ lockErr: '마스터 비밀번호를 입력해 주세요.', lockShakeN: get().lockShakeN + 1 })
        return
      }
      set({ unlocking: true, lockErr: '' })
      try {
        await vaultApi.unlock(get().lockPw)
        set({ screen: 'app', locked: false, unlocking: false, lockPw: '' })
        get().loadVault()
        // 해제 후에도 값은 마스킹 유지 — 항목별 클릭 시에만 4초간 표시(일괄 노출 금지).
        get().showToast('잠금 해제됨 — 값은 항목을 클릭하면 4초간 표시됩니다')
      } catch (e) {
        let msg = vaultErrorText(e, '잠금 해제 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요.')
        if (e instanceof VaultApiError) {
          if (e.status === 401) msg = '마스터 비밀번호가 올바르지 않아요.'
          else if (e.status === 429)
            msg = `시도가 많아요 — ${e.retryAfter ?? '잠시'}초 후 다시 시도하세요.`
        }
        set({ unlocking: false, lockErr: msg, lockShakeN: get().lockShakeN + 1 })
      }
    },
    lockNow: async () => {
      // 값 캐시(공개된 full)를 즉시 비우고 백엔드 세션도 잠근다.
      set((s) => ({
        locked: true,
        revealed: {},
        envOpen: false,
        vault: s.vault.map((v) => ({ ...v, full: '' })),
      }))
      try {
        await vaultApi.lock()
      } catch {
        /* 네트워크 실패해도 로컬은 잠금 표시 */
      }
      get().showToast('금고가 잠겼습니다')
    },
    gotoLockScreen: () => set({ screen: 'lock', lockPw: '', lockErr: '' }),

    // ── 입력 ──
    setUrl: (v) => set({ urlVal: v }),
    setText: (v) => set({ textVal: v }),
    setMemo: (v) => set({ memoVal: v }),
    setProj: (v) => set({ projVal: v }),
    setDragOver: (v) => set({ dragOver: v }),
    attachImage: (dataUrl, name) => set({ attachedImage: dataUrl, attachedName: name }),
    attachSample: () => set({ attachedImage: 'sample', attachedName: 'sample-screenshot.png' }),
    removeImage: () => set({ attachedImage: null, attachedName: '' }),
    handlePasteImage: (dataUrl) =>
      set({ attachedImage: dataUrl, attachedName: '붙여넣은 스크린샷.png' }),
    startAnalyze: async () => {
      if (get().analyzing) return
      const s = get()
      const text = s.textVal.trim()
      const url = s.urlVal.trim()
      const parts: string[] = []
      let img = s.attachedImage
      if (!img && !text && !url) img = 'sample'
      if (img) parts.push(img === 'sample' ? '샘플 스크린샷 1장' : '스크린샷 1장')
      if (url) parts.push('URL 1건')
      if (text) parts.push('텍스트')
      const memo = s.memoVal.trim()
      const project = s.projVal.trim()
      set({
        analyzing: true,
        ocrProgress: null,
        dragOver: false,
        sourceLabel: parts.join(' · '),
        analyzedImage: img,
        apiError: null,
        unknowns: [],
      })

      // 실제 스크린샷이 있으면 이미지 자체를 로컬 백엔드 OCR(RapidOCR, CORE-3)에 보내
      // OCR→분류를 한 번에 받는다 — 이미지는 이 기기(127.0.0.1)를 떠나지 않는다.
      if (img && img !== 'sample') {
        try {
          const blob = await (await fetch(img)).blob()
          const resp = await analyzeImageApi(blob, { url: url || undefined, text: text || undefined })
          if (!get().analyzing) return
          const { results, unknowns } = toAnalysisResults(resp.items, memo, project)
          set({ analyzing: false, analyzed: true, results, unknowns })
          // 부팅 후 Ollama가 뒤늦게 켜졌을 수 있으니 실제 스크린샷 분석마다 가용 여부를 다시 확인
          // (버튼이 부팅 시 확인 결과에 영구히 묶이지 않도록 — fire-and-forget, 폴링 아님).
          void get().checkExplainAvailable()
        } catch (e) {
          if (!get().analyzing) return
          if (!(e instanceof ApiError)) console.error('[KeyLens] 이미지 분석 요청 실패:', e)
          const results = freshResults().map((r) => ({ ...r, memo, project }))
          const msg = e instanceof ApiError ? e.message : 'KeyLens에 연결할 수 없어요'
          set({ analyzing: false, analyzed: true, results, unknowns: [], apiError: msg })
          get().showToast(`${msg} — 샘플 결과로 시연합니다`)
        }
        return
      }

      // 분석할 소스가 아무것도 없으면(샘플 스크린샷) 샘플 목업으로 시연.
      if (!text && !url) {
        await new Promise((r) => setTimeout(r, Math.max(200, ANALYZE_SECONDS * 1000)))
        if (!get().analyzing) return
        const results = freshResults().map((r) => ({ ...r, memo, project }))
        set({ analyzing: false, analyzed: true, results, unknowns: [] })
        return
      }

      // 백엔드 Stage1(값)+Stage2(맥락) 분류 호출(텍스트·URL만, 이미지 없음).
      try {
        const resp = await analyzeApi({
          text: text || undefined,
          url: url || undefined,
        })
        if (!get().analyzing) return
        const { results, unknowns } = toAnalysisResults(resp.items, memo, project)
        set({ analyzing: false, analyzed: true, results, unknowns })
      } catch (e) {
        if (!get().analyzing) return
        // 백엔드 미연결 → 데모가 끊기지 않게 샘플 목업으로 폴백.
        if (!(e instanceof ApiError)) console.error('[KeyLens] 분석 요청 실패:', e)
        const results = freshResults().map((r) => ({ ...r, memo, project }))
        const msg = e instanceof ApiError ? e.message : 'KeyLens에 연결할 수 없어요'
        set({ analyzing: false, analyzed: true, results, unknowns: [], apiError: msg })
        get().showToast(`${msg} — 샘플 결과로 시연합니다`)
      }
    },
    resetResults: () =>
      set({
        analyzed: false,
        analyzing: false,
        ocrProgress: null,
        results: [],
        unknowns: [],
        apiError: null,
        attachedImage: null,
        attachedName: '',
        analyzedImage: null,
        urlVal: '',
        textVal: '',
        memoVal: '',
        projVal: '',
      }),

    // ── 직접 입력 탭 ──
    setInputMode: (m) => set({ inputMode: m }),
    setManualField: (id, field, v) => {
      set((s) => {
        const rows = s.manualRows.map((r) => (r.id === id ? { ...r, [field]: v } : r))
        return { manualRows: ensureTrailingEmptyRow(rows, id) }
      })
    },
    splitManualField: (id, field) => {
      const row = get().manualRows.find((r) => r.id === id)
      if (!row) return
      const parsed = splitKeyValue(row[field])
      if (!parsed) return
      set((s) => {
        const rows = s.manualRows.map((r) =>
          r.id === id ? { ...r, name: parsed.name, value: parsed.value } : r,
        )
        return { manualRows: ensureTrailingEmptyRow(rows, id) }
      })
    },
    addManualRow: () =>
      set((s) => ({
        manualRows: [...s.manualRows, { id: crypto.randomUUID(), name: '', value: '' }],
      })),
    removeManualRow: (id) =>
      set((s) => ({
        manualRows: s.manualRows.length <= 1 ? s.manualRows : s.manualRows.filter((r) => r.id !== id),
      })),
    saveManualRows: async () => {
      const rows = get().manualRows.filter((r) => r.name.trim() && r.value.trim())
      if (!rows.length) {
        get().showToast('저장할 키/값을 먼저 입력해 주세요')
        return
      }
      const project = (get().projVal || '').trim() || null
      const memo = get().memoVal || null
      let saved = 0
      const savedIds: string[] = []
      for (const r of rows) {
        const name = r.name.trim()
        const value = r.value.trim()
        const found = findServiceByVarName(name)
        try {
          await vaultApi.add({
            service: found ? SERVICE_TO_ID[found.service] : null,
            kind: found ? found.type.v : null,
            official_name: name,
            value,
            label: found ? found.type.label : null,
            project,
            memo,
            expires_at: jwtExp(value),
          })
          saved++
          savedIds.push(r.id)
        } catch (e) {
          if (e instanceof VaultApiError && e.status === 401) {
            get().showToast('금고가 잠겨 저장할 수 없어요 — 잠금을 해제하세요')
            break
          }
          get().showToast(vaultErrorText(e, `${name} 저장 실패 — 잠시 후 다시 시도해 보세요`))
        }
      }
      if (saved) {
        set((s) => {
          const remaining = s.manualRows.filter((r) => !savedIds.includes(r.id))
          return {
            manualRows: remaining.length ? remaining : [{ id: crypto.randomUUID(), name: '', value: '' }],
          }
        })
        await get().loadVault()
        get().showToast(`${saved}개 저장됨 — AES-256-GCM 암호화`)
      }
    },

    // ── 결과 카드 ──
    patchResult: (id, patch) =>
      set((s) => ({
        results: s.results.map((r) => (r.id === id ? { ...r, ...patch } : r)),
      })),
    pickOption: (id, k) => get().patchResult(id, { typeKey: k }),
    setType: (id, v) => {
      if (v) get().patchResult(id, { typeKey: v })
    },
    save: async (id, force = false) => {
      // 백엔드 장애 폴백(샘플 목업) 결과는 진짜 분류가 아니다 — 보관함 오염 방지.
      if (get().apiError) {
        get().showToast('지금은 샘플 결과라 저장할 수 없어요 — 서버를 켜고 다시 분석해 주세요')
        return
      }
      const r = get().results.find((x) => x.id === id)
      if (!r) return
      const t = TYPE_MAP[r.service].find((t) => t.v === r.typeKey)
      if (!t) return
      if (!force) {
        const dup = findDup(r, t.var)
        if (dup) {
          set({ dupTarget: { resultId: id, existing: dup, varName: t.var } })
          return
        }
      }
      const jwtExpiry = jwtExp(r.full) // JWT면 만료일 자동 추출(TRUST-2)
      try {
        await vaultApi.add({
          service: SERVICE_TO_ID[r.service],
          kind: t.v,
          official_name: t.var,
          value: r.full,
          label: t.label,
          project: (r.project || '').trim() || null,
          memo: r.memo || null,
          expires_at: jwtExpiry,
        })
        set((s) => ({ results: s.results.filter((x) => x.id !== id), dupTarget: null }))
        await get().loadVault()
        get().showToast(
          t.var +
            ' 저장됨 — AES-256-GCM 암호화' +
            (jwtExpiry ? ` · JWT 만료일 자동 감지(${jwtExpiry})` : ''),
        )
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) {
          set({ dupTarget: null })
          get().showToast('금고가 잠겨 저장할 수 없어요 — 잠금을 해제하세요')
        } else {
          get().showToast(vaultErrorText(e, '저장 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요'))
        }
      }
    },
    confirmDup: () => {
      const d = get().dupTarget
      if (d) get().save(d.resultId, true)
    },
    cancelDup: () => set({ dupTarget: null }),
    saveAll: async () => {
      if (get().apiError) {
        get().showToast('지금은 샘플 결과라 저장할 수 없어요 — 서버를 켜고 다시 분석해 주세요')
        return
      }
      const savable = get().results.filter((r) =>
        TYPE_MAP[r.service].some((t) => t.v === r.typeKey),
      )
      if (!savable.length) {
        get().showToast('확인 필요 항목의 종류를 먼저 선택해 주세요')
        return
      }
      let saved = 0
      let dupCount = 0
      const savedIds: string[] = []
      for (const r of savable) {
        const t = TYPE_MAP[r.service].find((tt) => tt.v === r.typeKey)!
        if (findDup(r, t.var)) {
          dupCount++
          continue
        }
        try {
          await vaultApi.add({
            service: SERVICE_TO_ID[r.service],
            kind: t.v,
            official_name: t.var,
            value: r.full,
            label: t.label,
            project: (r.project || '').trim() || null,
            memo: r.memo || null,
            expires_at: jwtExp(r.full), // JWT면 만료일 자동(TRUST-2)
          })
          saved++
          savedIds.push(r.id)
          await get().loadVault() // dup 판정이 최신 목록을 보도록 갱신
        } catch (e) {
          if (e instanceof VaultApiError && e.status === 401) {
            get().showToast('금고가 잠겨 저장할 수 없어요 — 잠금을 해제하세요')
            break
          }
        }
      }
      const remaining = get().results.filter((r) => !savedIds.includes(r.id))
      const dupMarked = remaining.map((r) => {
        const t = TYPE_MAP[r.service].find((tt) => tt.v === r.typeKey)
        if (t && findDup(r, t.var)) {
          return {
            ...r,
            dupNote: '이미 보관 중인 키예요 — [확정 후 저장]을 누르면 추가 여부를 물어봅니다.',
          }
        }
        return r
      })
      set({ results: dupMarked })
      const parts = [saved + '개 저장됨']
      if (dupCount) parts.push('중복 ' + dupCount + '건은 카드에서 개별 확인')
      get().showToast(parts.join(' · '))
    },

    // ── 보관함 ──
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
    reveal: async (id) => {
      if (get().locked) {
        get().showToast('잠금 상태에서는 값을 볼 수 없어요 — 먼저 잠금을 해제하세요')
        return
      }
      const revealed = { ...get().revealed }
      if (revealed[id]) {
        // 숨기기 — 캐시된 값도 지운다(메모리 노출 최소화).
        delete revealed[id]
        set((s) => ({
          revealed,
          vault: s.vault.map((it) => (it.id === id ? { ...it, full: '' } : it)),
        }))
        if (revealTimers[id]) clearTimeout(revealTimers[id])
        return
      }
      try {
        const { value } = await vaultApi.value(Number(id))
        set((s) => ({
          revealed: { ...s.revealed, [id]: true },
          vault: s.vault.map((it) => (it.id === id ? { ...it, full: value } : it)),
        }))
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) {
          set({ locked: true })
          get().gotoLockScreen()
          get().showToast('잠금 상태입니다 — 다시 인증해 주세요')
        } else {
          get().showToast('값을 불러오지 못했어요')
        }
        return
      }
      // 4초 후 자동 숨김(값 캐시 제거).
      revealTimers[id] = timer(() => {
        set((s) => {
          if (!s.revealed[id]) return {}
          const r2 = { ...s.revealed }
          delete r2[id]
          return { revealed: r2, vault: s.vault.map((it) => (it.id === id ? { ...it, full: '' } : it)) }
        })
      }, 4000)
    },
    copy: (text, label) => {
      if (get().locked) {
        get().showToast('잠금 상태에서는 복사할 수 없어요')
        return
      }
      try {
        void navigator.clipboard.writeText(text)
      } catch {
        /* noop */
      }
      // 30초 후 클립보드 자동 삭제 — 그 사이 사용자가 다른 것을 복사했으면 건드리지 않는다.
      if (clipClearT) clearTimeout(clipClearT)
      clipClearT = setTimeout(async () => {
        try {
          if ((await navigator.clipboard.readText()) === text) {
            await navigator.clipboard.writeText('')
            get().showToast('복사한 값을 클립보드에서 지웠어요')
          }
        } catch {
          /* readText 미지원·권한 거부·포커스 없음 — 삭제 생략(덮어쓰기 오동작 방지) */
        }
      }, CLIP_CLEAR_MS)
      get().showToast(label + ' · 30초 후 클립보드에서 지워져요')
    },
    setVaultField: (id, key, v) => {
      // 즉시 로컬 반영(반응성) + 디바운스 백엔드 저장(평문 메타만).
      set((s) => ({
        vault: s.vault.map((it) => (it.id === id ? { ...it, [key]: v } : it)),
      }))
      if (key !== 'project' && key !== 'memo' && key !== 'expiresAt') return
      if (metaSaveT[id]) clearTimeout(metaSaveT[id])
      metaSaveT[id] = setTimeout(() => {
        const cur = get().vault.find((x) => x.id === id)
        if (!cur) return
        void vaultApi
          .update(Number(id), {
            project: cur.project || null,
            memo: cur.memo || null,
            expires_at: cur.expiresAt,
          })
          .catch((e) => get().showToast(vaultErrorText(e, '메모 저장 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요')))
      }, 600)
    },
    openRotate: (it) => set({ rotateTarget: it }),
    cancelRotate: () => set({ rotateTarget: null }),
    confirmRotate: async (newValue) => {
      const t = get().rotateTarget
      if (!t) return
      const v = newValue.trim()
      if (!v) {
        get().showToast('새 값을 입력해 주세요')
        return
      }
      try {
        await vaultApi.rotate(Number(t.id), v)
        set({ rotateTarget: null })
        await get().loadVault()
        if (get().expandedId === t.id) get().loadHistory(t.id) // 이력 갱신(키 교체 기록)
        get().showToast(t.varName + ' 값을 교체했어요 — 옛 값은 폐기됨')
      } catch (e) {
        set({ rotateTarget: null })
        if (e instanceof VaultApiError && e.status === 401) {
          set({ locked: true })
          get().showToast('금고가 잠겨 교체할 수 없어요 — 잠금을 해제하세요')
        } else {
          get().showToast(vaultErrorText(e, '값 교체 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요'))
        }
      }
    },
    setDeleteTarget: (it) => set({ deleteTarget: it }),
    cancelDelete: () => set({ deleteTarget: null }),
    confirmDelete: async () => {
      const t = get().deleteTarget
      if (!t) return
      try {
        await vaultApi.remove(Number(t.id))
        set({ deleteTarget: null })
        await get().loadVault()
        get().showToast(t.varName + ' 삭제됨')
      } catch (e) {
        set({ deleteTarget: null })
        if (e instanceof VaultApiError && e.status === 401) {
          set({ locked: true })
          get().showToast('금고가 잠겨 삭제할 수 없어요 — 잠금을 해제하세요')
        } else {
          get().showToast(vaultErrorText(e, '삭제 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요'))
        }
      }
    },
    toggleExpanded: (id) => {
      const willExpand = get().expandedId !== id
      set({ expandedId: willExpand ? id : null })
      if (willExpand && !get().locked) get().loadHistory(id) // 펼칠 때 감사 이력 로드
    },
    verifyEntry: async (id) => {
      if (get().locked) {
        get().showToast('잠금 상태에서는 검증할 수 없어요 — 먼저 잠금을 해제하세요')
        return
      }
      const patch = (v: VaultItem['verify']) =>
        set((s) => ({ vault: s.vault.map((it) => (it.id === id ? { ...it, verify: v } : it)) }))
      patch({ status: 'unknown', detail: '검증 중…', checking: true })
      try {
        const res = await vaultApi.verify(Number(id))
        patch({ status: res.status, detail: res.detail })
        const msg: Record<string, string> = {
          active: '유효한 키입니다 — 서비스가 인정했어요',
          invalid: '거부된 키입니다 — 폐기되었거나 잘못된 값이에요',
          unknown: '판단 불가 — ' + res.detail,
          unsupported: res.detail,
        }
        get().showToast(msg[res.status] ?? res.detail)
        if (get().expandedId === id) get().loadHistory(id) // 검증도 감사 이력에 남음
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) {
          set({ locked: true })
          patch(undefined)
          get().showToast('금고가 잠겨 검증할 수 없어요 — 잠금을 해제하세요')
        } else {
          patch({ status: 'unknown', detail: '검증 요청 실패' })
          get().showToast(vaultErrorText(e, '검증 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요'))
        }
      }
    },

    // ── .env 내보내기 ──
    openEnv: () => {
      if (get().locked) {
        get().showToast('잠금 상태에서는 내보낼 수 없어요 — 먼저 잠금을 해제하세요')
        return
      }
      if (!envItems().length) {
        get().showToast('내보낼 항목이 없어요')
        return
      }
      set({ envOpen: true })
    },
    closeEnv: () => set({ envOpen: false }),
    envCopyAll: async () => {
      const items = await withValues(envItems())
      get().copy(envText(items), '.env 내용 복사됨')
    },
    envDownload: async () => {
      try {
        const items = await withValues(envItems())
        const blob = new Blob([envText(items) + '\n'], { type: 'text/plain' })
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = 'keylens.env'
        a.click()
        setTimeout(() => URL.revokeObjectURL(a.href), 5000)
        get().showToast('keylens.env 다운로드 — .gitignore에 추가하세요')
      } catch {
        get().showToast('다운로드에 실패했어요')
      }
    },
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
    loadEnvPreview: () => withValues(envItems()),

    // ── SYNC-0: 암호화 금고 내보내기/가져오기 ──
    exportVault: async () => {
      if (get().locked) {
        get().showToast('잠금 상태에서는 내보낼 수 없어요 — 먼저 잠금을 해제하세요')
        return
      }
      try {
        const bundle = await vaultApi.exportBundle()
        const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = `keylens-vault-${today()}.klvault.json`
        a.click()
        setTimeout(() => URL.revokeObjectURL(a.href), 5000)
        get().showToast('금고를 암호화 번들로 내보냈어요 — 마스터 비밀번호 없이는 열 수 없습니다')
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) {
          set({ locked: true })
          get().showToast('금고가 잠겨 내보낼 수 없어요 — 잠금을 해제하세요')
        } else {
          get().showToast(vaultErrorText(e, '내보내기 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요'))
        }
      }
    },
    openSync: () => set({ syncOpen: true }),
    closeSync: () => set({ syncOpen: false }),
    openEmailSync: () => set({ emailSyncOpen: true }),
    closeEmailSync: () => set({ emailSyncOpen: false }),
    emailExport: async (destEmail) => {
      if (get().locked) {
        get().showToast('잠금 상태에서는 내보낼 수 없어요 — 먼저 잠금을 해제하세요')
        return false
      }
      try {
        const bundle = await vaultApi.exportBundle()
        await requestEmailExport(destEmail, bundle)
        set({ emailSyncOpen: false })
        get().showToast('확인 메일을 보냈어요 — 메일함에서 링크를 클릭하면 실제 파일이 발송됩니다')
        return true
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) {
          set({ locked: true })
          get().showToast('금고가 잠겨 내보낼 수 없어요 — 잠금을 해제하세요')
        } else if (e instanceof SyncRelayError) {
          get().showToast(e.message)
        } else {
          get().showToast(vaultErrorText(e, '내보내기 실패 — 잠시 후 다시 시도해 보세요'))
        }
        return false
      }
    },
    importVault: async (file, password, mode) => {
      let bundle: import('@/api/types').VaultBundle
      try {
        bundle = JSON.parse(await file.text())
      } catch {
        get().showToast('파일을 읽을 수 없어요 — 올바른 금고 파일인지 확인하세요')
        return false
      }
      try {
        const res = await vaultApi.importBundle(bundle, password, mode)
        set({ syncOpen: false, locked: false })
        await get().loadVault()
        const tail = res.skipped ? ` · ${res.skipped}개 건너뜀(중복)` : ''
        get().showToast(
          (res.mode === 'replace' ? '금고 교체' : '병합') +
            ` 완료 — ${res.imported}개 가져옴${tail}`,
        )
        return true
      } catch (e) {
        // 잘못된 비밀번호(401)·손상/버전(422)은 백엔드 메시지를 그대로 보여준다. 기존 금고는 무손상.
        get().showToast(vaultErrorText(e, '가져오기 실패 — 잠시 후 다시 시도하거나 KeyLens를 재시작해 보세요'))
        return false
      }
    },

    // ── 화면 설명(EXPLAIN, 1단계) ──
    checkExplainAvailable: async () => {
      const available = await explainStatusApi()
      set({ explainAvailable: available })
    },
    openExplain: async () => {
      const img = get().analyzedImage
      if (!img || img === 'sample') {
        get().showToast('실제 스크린샷이 있을 때만 화면 설명을 볼 수 있어요')
        return
      }
      set({ explainOpen: true, explainLoading: true, explainBoxes: [] })
      try {
        const blob = await (await fetch(img)).blob()
        const boxes = await explainImageApi(blob)
        set({ explainLoading: false, explainBoxes: boxes })
      } catch (e) {
        set({ explainLoading: false, explainOpen: false })
        get().showToast(e instanceof ApiError ? e.message : '화면 설명을 불러오지 못했어요')
      }
    },
    closeExplain: () => set({ explainOpen: false, explainBoxes: [] }),

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

    resetProto: () => {
      set({
        vault: [],
        screen: 'setup',
        view: 'input',
        analyzed: false,
        analyzing: false,
        ocrProgress: null,
        results: [],
        unknowns: [],
        apiError: null,
        locked: false,
        search: '',
        projFilter: '',
        projectOpenOverrides: {},
        serviceTagFilter: new Set(),
        revealed: {},
        expandedId: null,
        attachedImage: null,
        attachedName: '',
        analyzedImage: null,
        urlVal: '',
        textVal: '',
        memoVal: '',
        projVal: '',
        pw: '',
        pw2: '',
        setupErr: '',
        lockPw: '',
        lockErr: '',
        resetVaultOpen: false,
        resetVaultPw: '',
        resetVaultErr: '',
        resettingVault: false,
        deleteTarget: null,
        dupTarget: null,
        rotateTarget: null,
        envOpen: false,
        syncOpen: false,
        pendingRequests: [],
        sdkProjects: [],
        selectedSdkProject: null,
        sdkDirs: [],
        newDirPath: '',
      })
    },
  }
})
