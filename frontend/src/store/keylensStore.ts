// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
//
// KeyLens 앱 상태 스토어.
// 프로토타입 KeyLens.dc.html의 DCLogic 클래스(state + 메서드)를 Zustand로 이식했다.
// 목업 로직(seed 데이터, 가짜 분석·저장)은 그대로 유지하며,
// 실제 백엔드(SPEC 5장: OCR·분류·암호화·SQLite)로 교체할 지점은 seed.ts / services.ts로 분리해 둔다.
import { create } from 'zustand'
import { analyzeApi, ApiError, vaultApi, VaultApiError } from '@/api/client'
import { metaToVaultItem, SERVICE_TO_ID, toAnalysisResults } from '@/api/map'
import { runOcr } from '@/ocr/ocr'
import { TYPE_MAP } from '@/data/services'
import { freshResults } from '@/data/seed'
import { envText, today } from '@/lib/format'
import type {
  AnalysisResult,
  DeleteTarget,
  DupTarget,
  Screen,
  UnknownItem,
  VaultItem,
  View,
} from '@/types'

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
  revealed: Record<string, boolean>
  expandedId: string | null

  // 다이얼로그 / 토스트
  deleteTarget: DeleteTarget
  dupTarget: DupTarget | null
  envOpen: boolean
  toast: string | null

  // ── 액션 ──
  showToast: (msg: string) => void
  cleanup: () => void
  /** 앱 시작 시 백엔드 금고 상태로 화면(설정/잠금/앱)을 결정. */
  boot: () => void
  /** 백엔드에서 금고 항목 메타데이터를 다시 불러온다. */
  loadVault: () => void
  /** 항목 값을 복호화해 클립보드에 복사(잠금 시 인증 유도). prefix 지정 시 `prefix+값`(.env 한 줄). */
  copyValue: (id: string, label: string, prefix?: string) => void

  goInput: () => void
  goVault: () => void

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
  handlePasteText: (text: string) => void
  startAnalyze: () => void
  resetResults: () => void

  patchResult: (id: string, patch: Partial<AnalysisResult>) => void
  pickOption: (id: string, k: string) => void
  setType: (id: string, v: string) => void
  save: (id: string, force?: boolean) => void
  confirmDup: () => void
  cancelDup: () => void
  saveAll: () => void

  setSearch: (v: string) => void
  setProjFilter: (v: string) => void
  reveal: (id: string) => void
  copy: (text: string, label: string) => void
  setVaultField: (id: string, key: keyof VaultItem, v: unknown) => void
  rotate: (id: string) => void
  setDeleteTarget: (it: VaultItem) => void
  cancelDelete: () => void
  confirmDelete: () => void
  toggleExpanded: (id: string) => void

  openEnv: () => void
  closeEnv: () => void
  envCopyAll: () => void
  envDownload: () => void
  envCopyGroup: (name: string) => void

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
  const findDup = (r: AnalysisResult, varName: string): VaultItem | undefined =>
    get().vault.find(
      (v) => v.varName === varName && (v.project || '') === (r.project || '').trim(),
    )

  // .env 내보내기용으로 각 항목의 값을 복호화해 채운다(잠금/실패 항목은 제외).
  const withValues = async (items: VaultItem[]): Promise<VaultItem[]> => {
    const out: VaultItem[] = []
    for (const it of items) {
      try {
        const { value } = await vaultApi.value(Number(it.id))
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
    revealed: {},
    expandedId: null,
    deleteTarget: null,
    dupTarget: null,
    envOpen: false,
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

    goInput: () => set({ view: 'input' }),
    goVault: () => set({ view: 'vault' }),

    // ── 부팅 / 금고 로딩 ──
    boot: async () => {
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
      } catch {
        // 백엔드 미연결 — 금고 기능은 백엔드가 필요하다. 설정 화면 + 안내.
        set({ screen: 'setup' })
        get().showToast('백엔드(:8003) 미연결 — 금고 기능은 백엔드를 켜야 동작해요')
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
        const { value } = await vaultApi.value(Number(id))
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

    // ── 설정(최초 실행) ──
    setPw: (v) => set({ pw: v, setupErr: '' }),
    setPw2: (v) => set({ pw2: v, setupErr: '' }),
    createVault: async () => {
      const { pw, pw2 } = get()
      if (pw.length < 8) {
        set({ setupErr: '비밀번호는 8자 이상이어야 해요.' })
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
            : '금고 생성 실패 — 백엔드(:8003)가 켜져 있는지 확인하세요.',
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
        let msg = '잠금 해제 실패 — 백엔드 연결을 확인하세요.'
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
    handlePasteText: (text) => {
      if (!get().analyzed && !get().analyzing) set({ textVal: text })
    },
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

      // 실제 스크린샷이면 브라우저 안에서 OCR(CORE-3) → 라벨 보존 텍스트. 이미지는 기기를 떠나지 않는다.
      let ocrText = ''
      // OCR 이 이어붙인 이음매(불확실 지점) — 값 문자열 → 표식 인덱스. 결과 카드가 "여기 확인" 표시.
      const ocrMarks = new Map<string, number[]>()
      if (img && img !== 'sample') {
        set({ ocrProgress: 0 })
        try {
          const rec = await runOcr(img, (p) => {
            if (get().analyzing) set({ ocrProgress: p.progress })
          })
          ocrText = rec.text
          for (const f of rec.flagged) ocrMarks.set(f.text, f.marks)
        } catch {
          get().showToast('스크린샷 인식 실패 — 텍스트·URL만 분석합니다')
        }
        if (!get().analyzing) return // 중간에 리셋됨
        set({ ocrProgress: null })
      }

      // OCR 텍스트 + 직접 입력 텍스트를 합쳐 Stage2 라벨 페어링에 먹인다.
      const analyzeText = [ocrText, text].filter(Boolean).join('\n')

      // 분석할 소스가 아무것도 없으면(샘플 이미지·OCR 빈 결과) 샘플 목업으로 시연.
      if (!analyzeText && !url) {
        await new Promise((r) => setTimeout(r, Math.max(200, ANALYZE_SECONDS * 1000)))
        if (!get().analyzing) return
        const results = freshResults().map((r) => ({ ...r, memo, project }))
        set({ analyzing: false, analyzed: true, results, unknowns: [] })
        return
      }

      // 백엔드 Stage1(값)+Stage2(맥락) 분류 호출.
      try {
        const resp = await analyzeApi({
          text: analyzeText || undefined,
          url: url || undefined,
        })
        if (!get().analyzing) return
        const { results, unknowns } = toAnalysisResults(resp.items, memo, project)
        // OCR 이 이어붙인 값에 "여기 확인" 표식을 달고, 있으면 토스트로 알린다(값은 복붙 권장).
        let flaggedCount = 0
        for (const r of results) {
          const marks = ocrMarks.get(r.full)
          if (marks?.length) {
            r.ocrUncertain = marks
            flaggedCount++
          }
        }
        set({ analyzing: false, analyzed: true, results, unknowns })
        if (flaggedCount) {
          get().showToast('OCR가 값 일부를 이어붙였어요 — 원본을 복사해 확인하세요')
        }
      } catch (e) {
        if (!get().analyzing) return
        // 백엔드 미연결 → 데모가 끊기지 않게 샘플 목업으로 폴백.
        const results = freshResults().map((r) => ({ ...r, memo, project }))
        const msg = e instanceof ApiError ? e.message : '백엔드 연결 실패'
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
        get().showToast('백엔드 미연결 — 샘플 목업 결과는 저장할 수 없어요')
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
      try {
        await vaultApi.add({
          service: SERVICE_TO_ID[r.service],
          kind: t.v,
          official_name: t.var,
          value: r.full,
          label: t.label,
          project: (r.project || '').trim() || null,
          memo: r.memo || null,
        })
        set((s) => ({ results: s.results.filter((x) => x.id !== id), dupTarget: null }))
        await get().loadVault()
        get().showToast(t.var + ' 저장됨 — AES-256-GCM으로 암호화되어 이 기기에만 보관')
      } catch (e) {
        if (e instanceof VaultApiError && e.status === 401) {
          set({ dupTarget: null })
          get().showToast('금고가 잠겨 저장할 수 없어요 — 잠금을 해제하세요')
        } else {
          get().showToast('저장 실패 — 백엔드 연결을 확인하세요')
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
        get().showToast('백엔드 미연결 — 샘플 목업 결과는 저장할 수 없어요')
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
          .catch(() => get().showToast('메모 저장 실패 — 백엔드 연결을 확인하세요'))
      }, 600)
    },
    rotate: (id) => {
      // 회전 이력 저장은 백엔드 스키마 미지원 — 이 세션 표시용(재시작 시 사라짐).
      const d = today()
      set((s) => ({
        vault: s.vault.map((it) =>
          it.id === id
            ? { ...it, history: [...(it.history || []), { date: d, event: '키 회전' }] }
            : it,
        ),
      }))
      get().showToast('회전 기록 추가(이 세션에만 표시 — 이력 저장은 후속)')
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
          get().showToast('삭제 실패 — 백엔드 연결을 확인하세요')
        }
      }
    },
    toggleExpanded: (id) => set((s) => ({ expandedId: s.expandedId === id ? null : id })),

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
    envCopyGroup: async (name) => {
      const items = await withValues(envItems().filter((i) => i.service === name))
      get().copy(envText(items), name + ' 그룹 .env 복사됨')
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
        deleteTarget: null,
        dupTarget: null,
        envOpen: false,
      })
    },
  }
})
