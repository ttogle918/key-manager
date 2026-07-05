// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { SERVICE_ORDER, SVC_META } from '@/data/services'
import { expiryInfo } from '@/lib/format'
import { useKeylens } from '@/store/keylensStore'
import { useProjectNames } from '@/store/selectors'
import { VaultRow } from '@/components/vault/VaultRow'
import type { VaultItem } from '@/types'

/** 화면 2: 조회 대시보드(보관함). */
export function VaultScreen() {
  const s = useKeylens()
  const projectNames = useProjectNames()
  const { vault, search, projFilter, locked } = s

  const q = search.trim().toLowerCase()
  const match = (it: VaultItem) =>
    (!projFilter || (it.project || '') === projFilter) &&
    (!q ||
      it.varName.toLowerCase().includes(q) ||
      it.type.toLowerCase().includes(q) ||
      it.service.toLowerCase().includes(q) ||
      (it.memo || '').toLowerCase().includes(q) ||
      (it.context || '').toLowerCase().includes(q) ||
      (it.project || '').toLowerCase().includes(q))

  // 만료 임박(≤14일)·만료 항목을 각 그룹 상단으로. 그 외는 기존 순서 유지(TRUST-2).
  const urgency = (v: VaultItem): number => {
    const e = expiryInfo(v.expiresAt)
    return e && (e.expired || e.days <= 14) ? e.days : Infinity
  }
  const groups = SERVICE_ORDER.map((name) => ({
    name,
    meta: SVC_META[name],
    items: vault
      .filter((v) => v.service === name && match(v))
      .sort((a, b) => urgency(a) - urgency(b)),
  })).filter((g) => g.items.length > 0)

  const vaultEmpty = vault.length === 0
  const noMatches = vault.length > 0 && groups.length === 0

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
          onChange={(e) => s.setProjFilter(e.target.value)}
          className="max-w-[170px] cursor-pointer rounded-lg border border-border bg-surface px-[10px] py-[9px] text-[12.5px] text-fg-soft outline-none"
        >
          <option value="">전체 프로젝트</option>
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

      {/* 서비스별 그룹 */}
      {groups.map((g) => (
        <section
          key={g.name}
          className="mb-4 overflow-hidden rounded-xl border border-line bg-panel"
        >
          <header className="flex items-center gap-[10px] border-b border-line bg-panel-head px-4 py-[11px]">
            <div
              className="flex size-6 flex-none items-center justify-center rounded-[6px] text-[12px] font-extrabold"
              style={{ background: g.meta.bg, color: g.meta.fg }}
            >
              {g.meta.tile}
            </div>
            <span className="text-[13.5px] font-semibold">{g.name}</span>
            <span className="text-[11.5px] text-dim">{g.items.length}개</span>
            <div className="ml-auto">
              <button
                type="button"
                onClick={() => s.envCopyGroup(g.name)}
                title="이 그룹을 .env 형식으로 복사"
                className="cursor-pointer rounded-[6px] border border-border bg-none px-[9px] py-1 font-mono text-[10.5px] font-semibold text-faint hover:border-border-strong hover:text-fg-soft"
              >
                .env 복사
              </button>
            </div>
          </header>
          {g.items.map((it) => (
            <VaultRow key={it.id} it={it} />
          ))}
        </section>
      ))}
    </div>
  )
}
