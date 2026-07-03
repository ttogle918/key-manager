// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
//
// KeyLens 앱 상태 스토어.
// 프로토타입 KeyLens.dc.html의 DCLogic 클래스(state + 메서드)를 Zustand로 이식했다.
// 목업 로직(seed 데이터, 가짜 분석·저장)은 그대로 유지하며,
// 실제 백엔드(SPEC 5장: OCR·분류·암호화·SQLite)로 교체할 지점은 seed.ts / services.ts로 분리해 둔다.
import { create } from 'zustand'
import { TYPE_MAP } from '@/data/services'
import { freshResults, seedVault } from '@/data/seed'
import { envText, today } from '@/lib/format'
import type {
  AnalysisResult,
  DeleteTarget,
  DupTarget,
  Screen,
  TypeOption,
  VaultItem,
  View,
} from '@/types'

/** 분석 시뮬레이션 시간(초). 실제 앱에선 백엔드 응답 시간으로 대체. */
const ANALYZE_SECONDS = 1.4
/** 잠금 해제 후 값이 자동 재마스킹되기까지의 시간(초). */
const REMASK_SECONDS = 5

// ── 비반응(non-reactive) 타이머 핸들 ──
let timers: ReturnType<typeof setTimeout>[] = []
let remaskCd: ReturnType<typeof setInterval> | null = null
let toastT: ReturnType<typeof setTimeout> | null = null
const revealTimers: Record<string, ReturnType<typeof setTimeout>> = {}

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
  justUnlocked: boolean
  remaskLeft: number

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
  analyzed: boolean
  results: AnalysisResult[]
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

  const findDup = (r: AnalysisResult, varName: string): VaultItem | undefined =>
    get().vault.find(
      (v) =>
        v.full === r.full ||
        (v.varName === varName && (v.project || '') === (r.project || '').trim()),
    )

  const vaultItemFrom = (r: AnalysisResult, t: TypeOption): VaultItem => {
    const d = today()
    const optionEvidence =
      r.typeKey && r.options
        ? (r.options.find((o) => o.k === r.typeKey) || { evidence: '' }).evidence
        : ''
    return {
      id: 'v_' + r.id + '_' + timers.length + '_' + get().vault.length,
      service: r.service,
      type: t.label,
      varName: t.var,
      masked: r.masked,
      full: r.full,
      addedAt: d,
      project: (r.project || '').trim(),
      context: r.context || optionEvidence || '',
      memo: r.memo || '',
      sourceImage: get().analyzedImage || null,
      expiresAt: null,
      history: [{ date: d, event: '등록' }],
      meta: { ...r.meta, confirmed_as: t.var, saved_at: d },
    }
  }

  const envItems = (): VaultItem[] => {
    const s = get()
    return s.vault.filter((v) => !s.projFilter || (v.project || '') === s.projFilter)
  }

  const startRemask = () => {
    const secs = Math.max(2, Math.round(REMASK_SECONDS))
    if (remaskCd) clearInterval(remaskCd)
    set({ justUnlocked: true, remaskLeft: secs })
    remaskCd = setInterval(() => {
      const left = get().remaskLeft - 1
      if (left <= 0) {
        if (remaskCd) clearInterval(remaskCd)
        set({ justUnlocked: false, remaskLeft: 0, revealed: {} })
        get().showToast('값이 다시 마스킹되었습니다')
      } else {
        set({ remaskLeft: left })
      }
    }, 1000)
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
    justUnlocked: false,
    remaskLeft: 0,
    dragOver: false,
    urlVal: '',
    textVal: '',
    memoVal: '',
    projVal: '',
    attachedImage: null,
    attachedName: '',
    analyzing: false,
    analyzed: false,
    results: [],
    sourceLabel: '',
    analyzedImage: null,
    vault: seedVault(),
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
      if (remaskCd) clearInterval(remaskCd)
      if (toastT) clearTimeout(toastT)
      Object.values(revealTimers).forEach(clearTimeout)
    },

    goInput: () => set({ view: 'input' }),
    goVault: () => set({ view: 'vault' }),

    // ── 설정(최초 실행) ──
    setPw: (v) => set({ pw: v, setupErr: '' }),
    setPw2: (v) => set({ pw2: v, setupErr: '' }),
    createVault: () => {
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
      timer(() => {
        set({ screen: 'app', view: 'input', unlocking: false, pw: '', pw2: '', locked: false })
        get().showToast('금고 생성 완료 — 모든 데이터는 이 기기에만 저장됩니다')
      }, 650)
    },

    // ── 잠금 / 해제 ──
    setLockPw: (v) => set({ lockPw: v, lockErr: '' }),
    submitUnlock: () => {
      if (get().unlocking) return
      if (!get().lockPw) {
        set({ lockErr: '마스터 비밀번호를 입력해 주세요.', lockShakeN: get().lockShakeN + 1 })
        return
      }
      set({ unlocking: true, lockErr: '' })
      timer(() => {
        set({ screen: 'app', locked: false, unlocking: false, lockPw: '' })
        startRemask()
      }, 750)
    },
    lockNow: () => {
      if (remaskCd) clearInterval(remaskCd)
      set({ locked: true, revealed: {}, justUnlocked: false, remaskLeft: 0, envOpen: false })
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
    startAnalyze: () => {
      if (get().analyzing) return
      const s = get()
      const parts: string[] = []
      let img = s.attachedImage
      if (!img && !s.urlVal.trim() && !s.textVal.trim()) img = 'sample'
      if (img) parts.push(img === 'sample' ? '샘플 스크린샷 1장' : '스크린샷 1장')
      if (s.urlVal.trim()) parts.push('URL 1건')
      if (s.textVal.trim()) parts.push('텍스트')
      set({ analyzing: true, dragOver: false, sourceLabel: parts.join(' · '), analyzedImage: img })
      const ms = Math.max(200, ANALYZE_SECONDS * 1000)
      timer(() => {
        const memo = get().memoVal.trim()
        const project = get().projVal.trim()
        const results = freshResults().map((r) => ({ ...r, memo, project }))
        set({ analyzing: false, analyzed: true, results })
      }, ms)
    },
    resetResults: () =>
      set({
        analyzed: false,
        analyzing: false,
        results: [],
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
    save: (id, force = false) => {
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
      const item = vaultItemFrom(r, t)
      set((s) => ({
        vault: [...s.vault, item],
        results: s.results.filter((x) => x.id !== id),
        dupTarget: null,
      }))
      get().showToast(t.var + ' 저장됨 · AES-256 암호화 완료')
    },
    confirmDup: () => {
      const d = get().dupTarget
      if (d) get().save(d.resultId, true)
    },
    cancelDup: () => set({ dupTarget: null }),
    saveAll: () => {
      const savable = get().results.filter((r) =>
        TYPE_MAP[r.service].some((t) => t.v === r.typeKey),
      )
      if (!savable.length) {
        get().showToast('확인 필요 항목의 종류를 먼저 선택해 주세요')
        return
      }
      let vault = get().vault.slice()
      let dupCount = 0
      const savedIds: string[] = []
      savable.forEach((r) => {
        const t = TYPE_MAP[r.service].find((t) => t.v === r.typeKey)!
        const dup = vault.find(
          (v) =>
            v.full === r.full ||
            (v.varName === t.var && (v.project || '') === (r.project || '').trim()),
        )
        if (dup) {
          dupCount++
          return
        }
        vault = vault.concat([vaultItemFrom(r, t)])
        savedIds.push(r.id)
      })
      const remaining = get().results.filter((r) => !savedIds.includes(r.id))
      const dupMarked = remaining.map((r) => {
        const t = TYPE_MAP[r.service].find((t) => t.v === r.typeKey)
        if (
          t &&
          vault.find(
            (v) =>
              v.full === r.full ||
              (v.varName === t.var && (v.project || '') === (r.project || '').trim()),
          )
        ) {
          return {
            ...r,
            dupNote: '이미 보관 중인 키예요 — [확정 후 저장]을 누르면 추가 여부를 물어봅니다.',
          }
        }
        return r
      })
      set({ vault, results: dupMarked })
      const parts = [savedIds.length + '개 저장됨']
      if (dupCount) parts.push('중복 ' + dupCount + '건은 카드에서 개별 확인')
      get().showToast(parts.join(' · '))
    },

    // ── 보관함 ──
    setSearch: (v) => set({ search: v }),
    setProjFilter: (v) => set({ projFilter: v }),
    reveal: (id) => {
      if (get().locked) {
        get().showToast('잠금 상태에서는 값을 볼 수 없어요 — 먼저 잠금을 해제하세요')
        return
      }
      const revealed = { ...get().revealed }
      if (revealed[id]) {
        delete revealed[id]
        set({ revealed })
        return
      }
      revealed[id] = true
      set({ revealed })
      revealTimers[id] = timer(() => {
        const r2 = { ...get().revealed }
        if (r2[id]) {
          delete r2[id]
          set({ revealed: r2 })
        }
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
      get().showToast(label + ' · 30초 후 클립보드에서 지워져요')
    },
    setVaultField: (id, key, v) =>
      set((s) => ({
        vault: s.vault.map((it) => (it.id === id ? { ...it, [key]: v } : it)),
      })),
    rotate: (id) => {
      const d = today()
      set((s) => ({
        vault: s.vault.map((it) =>
          it.id === id
            ? { ...it, history: [...(it.history || []), { date: d, event: '키 회전' }] }
            : it,
        ),
      }))
      get().showToast('회전 기록이 추가되었습니다')
    },
    setDeleteTarget: (it) => set({ deleteTarget: it }),
    cancelDelete: () => set({ deleteTarget: null }),
    confirmDelete: () => {
      const t = get().deleteTarget
      if (!t) return
      set((s) => ({ vault: s.vault.filter((v) => v.id !== t.id), deleteTarget: null }))
      get().showToast(t.varName + ' 삭제됨')
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
    envCopyAll: () => get().copy(envText(envItems()), '.env 내용 복사됨'),
    envDownload: () => {
      try {
        const blob = new Blob([envText(envItems()) + '\n'], { type: 'text/plain' })
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
    envCopyGroup: (name) => {
      const items = envItems().filter((i) => i.service === name)
      get().copy(envText(items), name + ' 그룹 .env 복사됨')
    },

    resetProto: () => {
      if (remaskCd) clearInterval(remaskCd)
      set({
        vault: [],
        screen: 'setup',
        view: 'input',
        analyzed: false,
        analyzing: false,
        results: [],
        locked: false,
        justUnlocked: false,
        remaskLeft: 0,
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
