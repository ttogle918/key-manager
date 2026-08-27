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
