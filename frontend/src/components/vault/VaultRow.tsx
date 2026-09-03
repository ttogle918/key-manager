// SPDX-FileCopyrightText: 2026 [Your Name]
// SPDX-License-Identifier: MIT
import { useMemo, type ReactNode } from 'react'
import { ExposureBadge, KeyHelp } from '@/components/KeyHelp'
import {
  CONSOLE_URL,
  resolveIssueUrl,
  SERVICE_ORDER,
  SERVICE_TO_ID,
  TYPE_MAP,
  UNCLASSIFIED_SERVICE,
} from '@/data/services'
import { expiryInfo, fmtDate, mask } from '@/lib/format'
import { useKeylens } from '@/store/keylensStore'
import type { VaultItem, VerifyStatus } from '@/types'

/** 복사 아이콘. */
function CopyIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden="true">
      <rect x="4.5" y="4.5" width="8" height="8" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.3" />
      <path d="M9.5 2.5h-6a1 1 0 0 0-1 1v6" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

/** 보관함 항목 한 줄 + 상세 펼침. */
export function VaultRow({ it }: { it: VaultItem }) {
  const locked = useKeylens((s) => s.locked)
  const revealed = useKeylens((s) => s.revealed[it.id])
  const expanded = useKeylens((s) => s.expandedId === it.id)
  const reveal = useKeylens((s) => s.reveal)
  const copyValue = useKeylens((s) => s.copyValue)
  const openRotate = useKeylens((s) => s.openRotate)
  const verifyEntry = useKeylens((s) => s.verifyEntry)
  const toggleExpanded = useKeylens((s) => s.toggleExpanded)
  const setVaultField = useKeylens((s) => s.setVaultField)
  const changeVaultService = useKeylens((s) => s.changeVaultService)
  const vault = useKeylens((s) => s.vault)

  /**
   * 드롭다운을 "이미 금고에 있는 서비스"와 "새로 지정" 둘로 나눈다.
   * 목록에 이미 보이는 서비스로 옮기는 게 압도적으로 흔한 동작인데, 지식베이스 전체가
   * 한 줄로 나열되면 그게 묻힌다. 표시는 <optgroup> 으로 한다 - 브라우저가 그룹 라벨을
   * 굵게 렌더하고 스크린리더도 그룹명을 읽어준다. "<" 같은 기호를 붙이면 스크린리더가
   * "작다"로 읽어 오히려 나빠진다.
   */
  const [usedServices, freshServices] = useMemo(() => {
    const inVault = new Set(vault.map((v) => v.service))
    const pickable = SERVICE_ORDER.filter((s) => s !== UNCLASSIFIED_SERVICE)
    return [pickable.filter((s) => inVault.has(s)), pickable.filter((s) => !inVault.has(s))]
  }, [vault])
  const setDeleteTarget = useKeylens((s) => s.setDeleteTarget)

  const cur = TYPE_MAP[it.service]?.find((t) => t.var === it.varName)
  // 서비스 드롭다운의 현재 선택값. `cur` 는 변수명으로 찾기 때문에 사용자가 이름을 자기
  // 것으로 바꾼 항목(MY_GITHUB 등)에서는 못 맞힌다 - 여기서는 백엔드가 저장한 라벨로 찾는다.
  const typeKey = TYPE_MAP[it.service]?.find((t) => t.label === it.type)?.v ?? ''
  const canSee = !locked && !!revealed
  const hasRealImg = !!(it.sourceImage && it.sourceImage !== 'sample')
  const exp = expiryInfo(it.expiresAt)
  const showExp = exp && (exp.expired || exp.days <= 14)
  const urgent = exp && (exp.expired || exp.urgent)
  const expFg = urgent ? '#E5675C' : '#E3B341'
  const copyOp = locked ? 0.35 : 1
  const copyCursor = locked ? 'not-allowed' : 'pointer'

  return (
    <div className="border-t border-[#14181E]">
      <div className="grid grid-cols-[220px_1fr_auto] items-center gap-[14px] px-4 py-[11px] hover:bg-[#13171D]">
        {/* 종류 + 변수명. 이 칸을 눌러도 상세가 열린다 - 오른쪽 ▾ 버튼까지 가는 수고를 줄이는
            지름길이고, 버튼 자체는 그대로 남아 키보드 경로가 된다. */}
        <div
          onClick={() => toggleExpanded(it.id)}
          title={expanded ? '접기' : '상세 보기'}
          className="min-w-0 cursor-pointer"
        >
          <div className="flex items-center gap-[6px] text-[11.5px] text-muted-2">
            <span className="overflow-hidden text-ellipsis whitespace-nowrap">{it.type}</span>
            {cur?.exposure === 'secret' && <ExposureBadge exposure="secret" />}
          </div>
          <div className="mt-[2px] overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[12px] text-fg-soft">
            {it.varName}
          </div>
        </div>

        {/* 값(마스킹/공개 토글). 더블클릭은 회전 모달로 가는 지름길 - 값 교체는 재암호화와
            이력 기록이 따라야 해서 표 안에서 직접 고치지 않는다.
            onClick 의 detail===1 은 더블클릭의 두 번째 클릭을 막는다. reveal 은 백엔드 복호화
            호출이라, 막지 않으면 회전하려고 더블클릭할 때마다 복호화·접근기록이 2건씩 쌓인다. */}
        <div
          onClick={(e) => e.detail === 1 && reveal(it.id)}
          onDoubleClick={() => !locked && openRotate(it)}
          title={
            locked
              ? '잠금 해제 후 볼 수 있어요'
              : canSee
                ? '클릭하여 숨기기 · 전체 값이 필요하면 복사 버튼을 쓰세요'
                : '클릭하면 앞뒤 4글자만 4초간 표시 · 더블클릭하면 값 교체'
          }
          className="cursor-pointer overflow-hidden text-ellipsis whitespace-nowrap rounded font-mono text-[12.5px] hover:bg-surface"
          style={{ color: canSee ? '#A7E8C9' : '#727C89' }}
        >
          {/* 공개해도 앞뒤 4글자만 보여준다. 화면에서 확인해야 하는 건 "이게 그 키가 맞나"이지
              값 전체가 아니다. 전체가 필요한 경우(붙여넣기)는 복사 버튼이 담당하고, 그쪽은
              스토어를 거치지 않고 백엔드에서 바로 받아 클립보드로 간다.
              12자 미만 값은 mask() 가 통째로 가린다 - 짧은 값은 앞뒤 4글자만으로도 거의 다 드러난다. */}
          {canSee ? mask(it.full, 4, 4) : it.masked}
        </div>

        {/* 날짜 · 만료 · 복사 · 삭제 · 펼침 */}
        <div className="flex items-center justify-end gap-[6px]">
          <span className="whitespace-nowrap text-[10.5px] text-dim-2" title={`${fmtDate(it.addedAt, true)} 등록`}>
            {fmtDate(it.addedAt)}
          </span>
          {showExp && exp && (
            <span
              className="whitespace-nowrap rounded-[5px] border px-[7px] py-[2.5px] text-[10.5px] font-bold"
              style={{
                color: expFg,
                background: urgent ? 'rgba(229,103,92,.1)' : 'rgba(227,179,65,.1)',
                borderColor: urgent ? 'rgba(229,103,92,.3)' : 'rgba(227,179,65,.25)',
              }}
            >
              만료 {exp.label}
            </span>
          )}
          <button
            type="button"
            onClick={() => copyValue(it.id, it.varName + ' 복사됨')}
            title="복사"
            className="flex items-center gap-[5px] rounded-[6px] border border-border bg-chip px-[9px] py-[5.5px] text-[11.5px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
            style={{ opacity: copyOp, cursor: copyCursor }}
          >
            <CopyIcon />
            복사
          </button>
          <button
            type="button"
            onClick={() => setDeleteTarget(it)}
            title="삭제"
            className="cursor-pointer rounded-[6px] border border-transparent bg-none px-2 py-[5px] text-[12px] text-dim-2 hover:border-[rgba(229,103,92,.3)] hover:text-danger"
          >
            ✕
          </button>
          <button
            type="button"
            onClick={() => toggleExpanded(it.id)}
            title="상세 보기"
            className="cursor-pointer rounded-[6px] border border-transparent bg-none px-[7px] py-[5px] text-[11px] text-faint transition-transform hover:text-fg-soft"
            style={{ transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
          >
            ▾
          </button>
        </div>
      </div>

      {/* 상세 */}
      {expanded && (
        <div className="flex gap-4 border-t border-[#14181E] bg-[#0D1014] px-4 pb-4 pt-[14px] [animation:klFade_.15s]">
          <div className="w-[150px] flex-none">
            {/* 스크린샷에는 값이 평문으로 찍혀 있다 — 값과 동일한 공개 조건(canSee)으로만 표시. */}
            {hasRealImg && canSee ? (
              <div
                role="img"
                aria-label="원본 스크린샷"
                className="h-[96px] w-[150px] rounded-lg border border-border bg-cover bg-top"
                style={{ backgroundImage: `url(${it.sourceImage})` }}
              />
            ) : (
              <div className="flex h-[96px] w-[150px] items-center justify-center rounded-lg border border-border [background:repeating-linear-gradient(45deg,#12151A,#12151A_6px,#161B21_6px,#161B21_12px)]">
                <span className="px-2 text-center font-mono text-[10px] text-dim">
                  {hasRealImg
                    ? '가려짐 — 값 표시 시 공개'
                    : it.sourceImage === 'sample'
                      ? 'sample screenshot'
                      : '원본 없음'}
                </span>
              </div>
            )}
            <div className="mt-[6px] text-center text-[10.5px] text-dim">원본 스크린샷</div>
          </div>

          <div className="flex min-w-0 flex-1 flex-col gap-[10px]">
            <Row label="등록일">
              <span className="text-fg-soft">{fmtDate(it.addedAt, true)}</span>
            </Row>
            <Row label="컬렉션">
              <input
                value={it.project}
                onChange={(e) => setVaultField(it.id, 'project', e.target.value)}
                list="kl-projects"
                placeholder="컬렉션 없음"
                className="w-[180px] rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[6px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
              />
            </Row>
            {/* 서비스 재지정 - 분류기가 다 맞힐 수는 없으니 사용자가 고칠 수 있어야 한다.
                값은 재암호화 없이 그대로다(암호문의 AAD 는 official_name 뿐). 변수명은
                여기서 못 바꾼다 - 그건 재암호화가 필요해 별도 스펙이다. */}
            <Row label="서비스">
              <select
                aria-label={`${it.varName || '이 항목'} 의 서비스`}
                value={
                  it.service === UNCLASSIFIED_SERVICE || !typeKey
                    ? ''
                    : `${it.service}|${typeKey}`
                }
                onChange={(e) => {
                  const [svc, kind] = e.target.value.split('|')
                  const id = svc ? SERVICE_TO_ID[svc] : null
                  void changeVaultService(it.id, id ?? null, svc ? kind : null)
                }}
                className="w-[180px] cursor-pointer rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[6px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
              >
                <option value="">미지정</option>
                {usedServices.length > 0 && (
                  <optgroup label={`이미 있는 서비스 (${usedServices.length})`}>
                    {usedServices.map((svc) =>
                      (TYPE_MAP[svc] ?? []).map((t) => (
                        <option key={`${svc}|${t.v}`} value={`${svc}|${t.v}`}>
                          {svc} · {t.label}
                        </option>
                      )),
                    )}
                  </optgroup>
                )}
                {freshServices.length > 0 && (
                  <optgroup label="새로 지정">
                    {freshServices.map((svc) =>
                      (TYPE_MAP[svc] ?? []).map((t) => (
                        <option key={`${svc}|${t.v}`} value={`${svc}|${t.v}`}>
                          {svc} · {t.label}
                        </option>
                      )),
                    )}
                  </optgroup>
                )}
              </select>
            </Row>
            {it.context && (
              <Row label="컨텍스트">
                <span className="text-blue-soft">{it.context}</span>
              </Row>
            )}
            <Row label="메모">
              <input
                value={it.memo}
                onChange={(e) => setVaultField(it.id, 'memo', e.target.value)}
                placeholder="언제·왜 발급받은 키인지 메모"
                className="min-w-0 flex-1 rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[6px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
              />
            </Row>
            <Row label="만료일">
              <input
                type="date"
                value={it.expiresAt || ''}
                onChange={(e) => setVaultField(it.id, 'expiresAt', e.target.value || null)}
                className="rounded-[7px] border border-line-2 bg-surface-3 px-[10px] py-[5px] text-[12px] text-fg-soft outline-none focus:border-[rgba(62,207,142,.5)]"
              />
              {exp && (
                <span className="text-[11px] font-semibold" style={{ color: expFg }}>
                  {exp.expired ? '만료됨 — 회전하세요' : exp.days + '일 남음'}
                </span>
              )}
              {/* 만료 임박·만료 → 재발급 바로가기(GUIDE-2 TRUST-2 연동) */}
              {exp &&
                (exp.expired || exp.urgent) &&
                (() => {
                  const url = resolveIssueUrl(cur?.issueUrl || CONSOLE_URL[it.service], it.project)
                  return url ? (
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-[6px] border border-[rgba(227,179,65,.3)] bg-[rgba(227,179,65,.08)] px-[9px] py-[3px] text-[11px] font-semibold text-amber hover:brightness-110"
                    >
                      재발급 →
                    </a>
                  ) : null
                })()}
            </Row>
            <Row label="검증">
              <button
                type="button"
                onClick={() => verifyEntry(it.id)}
                disabled={locked || it.verify?.checking}
                title="서비스로 read-only 호출 1회 — 키가 살아있는지 확인(값은 노출되지 않아요)"
                className="flex-none cursor-pointer rounded-[7px] border border-border bg-chip px-[10px] py-[5px] text-[11px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft disabled:cursor-not-allowed disabled:opacity-50"
              >
                {it.verify?.checking ? '검증 중…' : '유효성 검증'}
              </button>
              {it.verify && !it.verify.checking && (
                <VerifyBadge status={it.verify.status} detail={it.verify.detail} />
              )}
              {/* 검증 실패(폐기·오타) → 재발급 바로가기(GUIDE-2 상태 연동) */}
              {it.verify?.status === 'invalid' &&
                (() => {
                  const url = resolveIssueUrl(cur?.issueUrl || CONSOLE_URL[it.service], it.project)
                  return url ? (
                    <a
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-[6px] border border-[rgba(229,103,92,.3)] bg-[rgba(229,103,92,.08)] px-[9px] py-[4px] text-[11px] font-semibold text-danger hover:brightness-110"
                    >
                      재발급 →
                    </a>
                  ) : null
                })()}
            </Row>
            <KeyHelp
              service={it.service}
              typeKey={cur?.v ?? ''}
              project={it.project}
            />
            <Row label="이력">
              <span className="min-w-0 flex-1 overflow-hidden text-ellipsis whitespace-nowrap text-[11.5px] text-muted-2">
                {(it.history || []).map((h) => h.date + ' ' + h.event).join(' · ') || '기록 없음'}
              </span>
              <button
                type="button"
                onClick={() => openRotate(it)}
                disabled={locked}
                title="키를 새로 발급받았다면 값을 교체하세요(옛 값 폐기)"
                className="flex-none cursor-pointer rounded-[7px] border border-border bg-chip px-[10px] py-[5px] text-[11px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft disabled:cursor-not-allowed disabled:opacity-50"
              >
                값 교체
              </button>
            </Row>
            <div className="flex items-start gap-2 text-[12px]">
              <span className="mt-2 w-[52px] flex-none text-dim">비고</span>
              <pre className="m-0 min-w-0 flex-1 whitespace-pre-wrap break-all rounded-[7px] border border-line bg-inset px-[11px] py-[9px] font-mono text-[10.5px] leading-[1.6] text-muted-2">
                {JSON.stringify(it.meta || {}, null, 2)}
              </pre>
            </div>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => copyValue(it.id, '.env 형식으로 복사됨', it.varName + '=')}
                className="rounded-[7px] border border-border bg-chip px-[11px] py-[6px] font-mono text-[11px] font-semibold text-muted hover:border-border-strong hover:text-fg-soft"
                style={{ opacity: copyOp, cursor: copyCursor }}
              >
                .env 형식 복사
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/** 검증 결과 뱃지 — 값은 담지 않고 상태만 색으로 표시. */
const VERIFY_UI: Record<VerifyStatus, { text: string; fg: string; bg: string; bd: string }> = {
  active: { text: '유효 ✓', fg: '#3ECF8E', bg: 'rgba(62,207,142,.1)', bd: 'rgba(62,207,142,.3)' },
  invalid: { text: '거부됨 ✕', fg: '#E5675C', bg: 'rgba(229,103,92,.1)', bd: 'rgba(229,103,92,.3)' },
  unknown: { text: '판단 불가', fg: '#E3B341', bg: 'rgba(227,179,65,.1)', bd: 'rgba(227,179,65,.25)' },
  unsupported: { text: '미지원', fg: '#727C89', bg: 'rgba(114,124,137,.1)', bd: 'rgba(114,124,137,.28)' },
}

function VerifyBadge({ status, detail }: { status: VerifyStatus; detail: string }) {
  const u = VERIFY_UI[status]
  return (
    <span
      title={detail}
      className="whitespace-nowrap rounded-[5px] border px-[8px] py-[2.5px] text-[10.5px] font-bold"
      style={{ color: u.fg, background: u.bg, borderColor: u.bd }}
    >
      {u.text}
    </span>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-[12px]">
      <span className="w-[52px] flex-none text-dim">{label}</span>
      {children}
    </div>
  )
}
